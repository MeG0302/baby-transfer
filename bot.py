import os
import requests
import time
from dotenv import load_dotenv
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.aerial.client import LedgerClient, NetworkConfig
from cosmpy.aerial.tx import Transaction
from cosmpy.crypto.keypairs import PrivateKey
from cosmpy.crypto.address import Address, AddressCodec
from bip32utils import BIP32Key
from mnemonic import Mnemonic

# Load environment variables
load_dotenv()

# Babylon Testnet RPC Endpoints
RPC_ENDPOINTS = [
    "https://babylon-testnet-rpc.polkachu.com",
    "https://rpc.babylon-2.btc.com",
    "https://babylon-testnet-rpc.nodes.guru"
]

def get_working_rpc():
    """Detects and returns the first live Babylon RPC"""
    for endpoint in RPC_ENDPOINTS:
        try:
            test_addr = "bbn1hf9zkqvtfwwfn7e3cw8zwenxgrhfkyqsth22fw"
            status = requests.get(f"{endpoint}/status", timeout=5)
            balance = requests.get(f"{endpoint}/cosmos/bank/v1beta1/balances/{test_addr}/by_denom?denom=ubbn", timeout=5)
            if status.status_code == 200 and balance.status_code in [200, 404]:
                print(f"✅ Verified RPC: {endpoint}")
                return endpoint
        except:
            continue
    raise ConnectionError("❌ No working RPC endpoint found.")

# Set working RPC
working_rpc = get_working_rpc()
BABYLON_CONFIG = NetworkConfig(
    chain_id="bbn-test-5",
    url=f"rest+{working_rpc}",
    fee_minimum_gas_price=0.0025,
    fee_denomination="ubbn",
    staking_denomination="ubbn",
)

def get_wallet_from_seed(seed_phrase):
    """Derives Babylon wallet with bbn1... prefix manually"""
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
        wallet = LocalWallet(private_key)

        codec = AddressCodec("bbn")
        wallet._address = codec.encode(Address(private_key.public_key()))

        return wallet
    except Exception as e:
        raise Exception(f"Wallet creation failed: {str(e)}")

def get_balance(address):
    """Gets the ubbn balance of a Babylon address"""
    for attempt in range(3):
        try:
            r = requests.get(f"{working_rpc}/cosmos/bank/v1beta1/balances/{address}/by_denom?denom=ubbn", timeout=10)
            if r.status_code == 200:
                return float(r.json()["balance"]["amount"])
            elif r.status_code == 404:
                return 0.0
            raise Exception(f"Status {r.status_code}")
        except Exception as e:
            if attempt == 2:
                raise Exception(f"Balance check failed: {e}")
            time.sleep(2)

def send_tokens(client, sender_wallet, recipient, amount, leave_amount=0.1):
    """Sends amount from sender to recipient if balance allows"""
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
        print(f"❌ Transaction failed: {e}")
        return False

def many_to_one(client):
    """Transfer from many wallets to one address"""
    print("\n🔀 MANY-TO-ONE TRANSFER MODE")
    try:
        with open("seed.txt") as f:
            seeds = [s.strip() for s in f if s.strip()]
    except FileNotFoundError:
        print("❌ seed.txt not found")
        return

    if not seeds:
        print("❌ No seed phrases found")
        return

    recipient = input("Enter recipient address: ").strip()
    if not recipient.startswith("bbn1"):
        print("❌ Invalid recipient address")
        return

    for seed in seeds:
        try:
            wallet = get_wallet_from_seed(seed)
            address = wallet.address()
            balance = get_balance(address)
            print(f"\n🏦 Wallet: {address}\n   Balance: {balance}ubbn")

            if balance > 0.1:
                send_tokens(client, wallet, recipient, balance)
            else:
                print("   Skipping - insufficient balance")
        except Exception as e:
            print(f"❌ Error processing wallet: {e}")

def one_to_many(client):
    """Send from one wallet to many addresses"""
    print("\n🔀 ONE-TO-MANY TRANSFER MODE")
    sender_seed = input("Enter sender seed phrase: ").strip()

    try:
        with open("wallet.txt") as f:
            recipients = [r.strip() for r in f if r.strip()]
    except FileNotFoundError:
        print("❌ wallet.txt not found")
        return

    if not recipients:
        print("❌ No recipient addresses found")
        return

    try:
        amount = float(input("Amount to send to each (in ubbn): ").strip())
        if amount <= 0:
            print("❌ Amount must be > 0")
            return
    except ValueError:
        print("❌ Invalid amount")
        return

    try:
        wallet = get_wallet_from_seed(sender_seed)
        balance = get_balance(wallet.address())
        total_needed = amount * len(recipients)

        print(f"\n👤 Sender: {wallet.address()}")
        print(f"   Balance: {balance}ubbn")
        print(f"   Needed: {total_needed}ubbn + 0.1 for fee")

        if balance < total_needed + 0.1:
            print("❌ Not enough funds")
            return

        for i, recipient in enumerate(recipients, 1):
            print(f"\nRecipient {i}/{len(recipients)}: {recipient}")
            send_tokens(client, wallet, recipient, amount)
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    try:
        client = LedgerClient(BABYLON_CONFIG)
        print("\n" + "=" * 40)
        print(" BABYLON-2 TOKEN TRANSFER BOT")
        print(f" Connected to: {working_rpc}")
        print("=" * 40)

        while True:
            print("\nOPTIONS:")
            print("1. Many → One (Consolidate)")
            print("2. One → Many (Distribute)")
            print("3. Exit")
            choice = input("Choose option (1/2/3): ").strip()

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
        print(f"\n❌ Fatal error: {e}")
    finally:
        print("\n✅ Done.")

if __name__ == "__main__":
    main()
