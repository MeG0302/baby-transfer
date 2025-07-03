import os
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.aerial.client import LedgerClient, NetworkConfig
from cosmpy.aerial.tx import Transaction
from cosmpy.crypto.keypairs import PrivateKey
from bip32utils import BIP32Key
from mnemonic import Mnemonic
from dotenv import load_dotenv
import hashlib

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

def get_wallet_from_seed(seed_phrase):
    """Create wallet from seed phrase using proper derivation"""
    # Generate seed from mnemonic
    mnemo = Mnemonic("english")
    seed = mnemo.to_seed(seed_phrase)
    
    # Derive private key (using BIP39/BIP32)
    bip32_root = BIP32Key.fromEntropy(seed)
    bip32_child = bip32_root.ChildKey(44 + BIP32Key.HARDEN).ChildKey(118 + BIP32Key.HARDEN).ChildKey(0 + BIP32Key.HARDEN).ChildKey(0).ChildKey(0)
    private_key_bytes = bip32_child.PrivateKey()
    
    # Create Cosmpy private key
    private_key = PrivateKey(private_key_bytes)
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
    
    tx = client.finalize_and_broadcast(tx, sender_wallet)
    print(f"✅ Sent {amount_to_send}ubbn to {recipient[:10]}...")
    print(f"   Tx Hash: {tx.tx_hash}")
    return True

# [Rest of the functions remain the same as previous versions]
# ... (many_to_one, one_to_many, main functions)

if __name__ == "__main__":
    main()
