import os
import csv
import time
from dotenv import load_dotenv
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.aerial.client import LedgerClient, NetworkConfig
from cosmpy.aerial.tx import Transaction
from cosmpy.aerial.tx_helpers import submit_signed_transaction

# Load env
load_dotenv()
RPC_URL = os.getenv("RPC_URL")
CHAIN_ID = os.getenv("CHAIN_ID")

# Load mnemonics
with open("mnemonics.txt", "r") as f:
    MNEMONICS = [line.strip() for line in f if line.strip()]

# Load wallets if needed
def load_recipients():
    with open("wallets.txt", "r") as f:
        return [line.strip() for line in f if line.strip()]

# Setup client
config = NetworkConfig(
    chain_id=CHAIN_ID,
    url=RPC_URL,
    fee_minimum_gas_price=0.025,
    fee_denomination="ubbn",
    staking_denomination="ubbn",
)
client = LedgerClient(config)

# Log setup
log_file = "log.csv"
if not os.path.exists(log_file):
    with open(log_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Sender", "Recipient", "Amount", "Status", "TX Hash", "Time"])

def log_tx(sender, recipient, amount, status, tx_hash="-"):
    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([sender, recipient, amount, status, tx_hash, time.strftime("%Y-%m-%d %H:%M:%S")])

# Convert to ubbn
def to_ubbn(bbn):
    return int(float(bbn) * 1_000_000)

# Send BBN
def send_tokens(sender_wallet, recipient, amount_bbn):
    sender_addr = str(sender_wallet.address())
    amount_ubbn = to_ubbn(amount_bbn)
    gas_fee = to_ubbn(0.025) * 2100

    balance = client.query_bank_balance(sender_addr, denom="ubbn").amount
    if balance < (amount_ubbn + gas_fee):
        print(f"❌ Skipping {sender_addr} - insufficient BBN")
        log_tx(sender_addr, recipient, amount_bbn, "Skipped: Low Balance")
        return

    tx = Transaction()
    tx.add_message(
        sender_wallet.bank_send(
            to_address=recipient,
            amount=amount_ubbn,
            denom="ubbn"
        )
    )
    tx = tx.with_sender(sender_addr)
    tx = tx.with_chain_id(CHAIN_ID)
    tx = tx.with_fee(gas=2100, amount=to_ubbn(0.025))
    tx_signed = tx.sign(sender_wallet)

    try:
        tx_resp = submit_signed_transaction(tx_signed, client)
        print(f"✅ Sent {amount_bbn} BBN from {sender_addr} to {recipient}")
        log_tx(sender_addr, recipient, amount_bbn, "Success", tx_resp.tx_hash)
    except Exception as e:
        print(f"❌ Failed from {sender_addr} → {recipient}: {str(e)}")
        log_tx(sender_addr, recipient, amount_bbn, "Failed", str(e))

# Main
def main():
    print("Choose mode:")
    print("1 - One-to-Many (1 sender to many recipients)")
    print("2 - Many-to-One (many senders to 1 recipient)")
    mode = input("Enter mode (1 or 2): ").strip()

    amount = input("💰 Enter amount of BBN to send from each wallet: ").strip()
    try:
        amount = float(amount)
        assert amount > 0
    except:
        print("Invalid amount.")
        return

    if mode == "1":
        recipients = load_recipients()
        sender_wallet = LocalWallet.from_mnemonic(MNEMONICS[0])
        for recipient in recipients:
            send_tokens(sender_wallet, recipient, amount)

    elif mode == "2":
        recipient = input("🎯 Enter the recipient wallet address: ").strip()
        for mnemonic in MNEMONICS:
            wallet = LocalWallet.from_mnemonic(mnemonic)
            send_tokens(wallet, recipient, amount)
    else:
        print("❌ Invalid mode")

if __name__ == "__main__":
    main()
