import os
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.aerial.client import LedgerClient, NetworkConfig
from cosmpy.aerial.tx import Transaction
from cosmpy.crypto.keypairs import PrivateKey
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Babylon Testnet configuration
BABYLON_CONFIG = NetworkConfig(
    chain_id="babylon-2",
    url="https://rpc.babylon-2.btc.com",
    fee_minimum_gas_price=0.0025,
    fee_denomination="ubbn",
    staking_denomination="ubbn",
)

def get_wallet_from_seed(seed_phrase):
    """Create wallet from seed phrase"""
    private_key = PrivateKey.from_seed_phrase(seed_phrase)
    return LocalWallet(private_key)

def get_balance(client, address):
    """Get Babylon token balance for an address"""
    return client.query_bank_balance(address)

def send_tokens(client, sender_wallet, recipient_address, amount, leave_amount=0.1):
    """Send tokens from one wallet to another"""
    sender_balance = client.query_bank_balance(sender_wallet.address())
    
    # Calculate amount to send (leave specified amount)
    if sender_balance <= leave_amount:
        print(f"Insufficient balance in {sender_wallet.address()} (balance: {sender_balance})")
        return False
    
    amount_to_send = min(amount, sender_balance - leave_amount)
    
    tx = Transaction()
    tx.add_bank_transfer(recipient_address, amount_to_send, "ubbn")
    
    # Sign and broadcast transaction
    tx = client.finalize_and_broadcast(tx, sender_wallet)
    print(f"Sent {amount_to_send} ubbn from {sender_wallet.address()} to {recipient_address}")
    print(f"Transaction hash: {tx.tx_hash}")
    return True

def many_to_one_transfer(client):
    """Transfer from many accounts to one account (consolidation)"""
    print("\n--- Many to One Transfer ---")
    
    # Read seed phrases from file
    try:
        with open("seed.txt", "r") as f:
            seed_phrases = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        print("Error: seed.txt file not found")
        return
    
    if not seed_phrases:
        print("Error: No seed phrases found in seed.txt")
        return
    
    # Get recipient address
    recipient_address = input("Enter recipient Babylon address: ").strip()
    
    # Process each wallet
    for seed in seed_phrases:
        try:
            wallet = get_wallet_from_seed(seed)
            balance = get_balance(client, wallet.address())
            
            print(f"\nWallet: {wallet.address()}")
            print(f"Balance: {balance} ubbn")
            
            if balance > 0.1:  # Leave 0.1 ubbn in wallet
                send_tokens(client, wallet, recipient_address, balance)
            else:
                print("Skipping - insufficient balance")
        except Exception as e:
            print(f"Error processing wallet: {e}")

def one_to_many_transfer(client):
    """Transfer from one account to many accounts (distribution)"""
    print("\n--- One to Many Transfer ---")
    
    # Get sender seed phrase
    sender_seed = input("Enter sender seed phrase: ").strip()
    if not sender_seed:
        print("Error: No seed phrase provided")
        return
    
    # Read recipient addresses from file
    try:
        with open("wallet.txt", "r") as f:
            recipient_addresses = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        print("Error: wallet.txt file not found")
        return
    
    if not recipient_addresses:
        print("Error: No recipient addresses found in wallet.txt")
        return
    
    # Get amount to send to each recipient
    try:
        amount_per_recipient = float(input("Enter amount to send to each recipient (in ubbn): ").strip())
    except ValueError:
        print("Error: Invalid amount")
        return
    
    # Get sender wallet
    try:
        sender_wallet = get_wallet_from_seed(sender_seed)
        sender_balance = get_balance(client, sender_wallet.address())
        
        print(f"\nSender: {sender_wallet.address()}")
        print(f"Balance: {sender_balance} ubbn")
        
        total_needed = amount_per_recipient * len(recipient_addresses)
        if sender_balance < total_needed + 0.1:  # Leave 0.1 ubbn in sender wallet
            print(f"Error: Insufficient balance. Need {total_needed} ubbn but have {sender_balance}")
            return
        
        # Send to each recipient
        for addr in recipient_addresses:
            send_tokens(client, sender_wallet, addr, amount_per_recipient)
            
    except Exception as e:
        print(f"Error: {e}")

def main():
    # Initialize client
    client = LedgerClient(BABYLON_CONFIG)
    
    print("Babylon Testnet Token Transfer Bot")
    print("--------------------------------")
    
    while True:
        print("\nOptions:")
        print("1 - From many accounts to one account (consolidation)")
        print("2 - From one account to many accounts (distribution)")
        print("3 - Exit")
        
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == "1":
            many_to_one_transfer(client)
        elif choice == "2":
            one_to_many_transfer(client)
        elif choice == "3":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
