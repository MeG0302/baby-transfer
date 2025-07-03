import os
import csv
import time
from dotenv import load_dotenv
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.aerial.client import LedgerClient, NetworkConfig
from cosmpy.aerial.tx import Transaction
from cosmpy.protos.cosmos.bank.v1beta1.tx_pb2 import MsgSend
from cosmpy.protos.cosmos.base.v1beta1.coin_pb2 import Coin

# Load .env variables
load_dotenv()
RPC_URL = os.getenv("RPC_URL")
CHAIN_ID = os.getenv("CHAIN_ID")

# Load mnemonics
with open("mnemonics.txt", "r") as f:
    MNEMONICS = [line.strip() for line in f if line.strip()]

# Load recipients list
def load_recipients():
    with open("wallets.txt", "r") as f:
        return [line.strip() for line in f if line.strip()]

# Network config
config = NetworkConfig(
    chain_id=CHAIN_ID,
    url=RPC_URL,
    fee_minimum_gas_price=0.001,
    fee_denomination="ubbn",
    staking_denomination="ubbn",
)
client = LedgerClient(config)

# Log file setup
log_file = "log.csv"
if not os.path.exists(log_file):
    with open(log_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Sender", "Recipient", "Amount", "Status", "TX Hash", "Time"])

def log_tx(sender, recipient, amount, status, tx_hash="-"):
    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([sender, recipient, amount, status, tx_hash, time.strftime("%Y-%m-%d %H:%M:%S")])

def to_ubbn(bbn):
    return int(float(bbn) * 1_000_000)

def send_tokens(sender_wallet, recipient, amount_bbn):
    sender_addr = str(sender_wallet.address())
    amount_ubbn = to_ubbn(amount_bbn)
    gas_limit = 80000
    gas_fee = to_ubbn(0.002)

    try:
        balance_obj = client.query_bank_balance(sender_addr, denom="ubbn")
        balance = int(balance_obj.amount)
        print(f"🧾 Balance of {sender_addr}: {balance / 1_000_000:.6f} BBN")
    except Exception as e:
        print(f"⚠️ Failed to fetch balance for {sender_addr}: {e}")
        log_tx(sender_addr, recipient, amount_bbn, "Failed: Balance Fetch", str(e))
        return

    if balance < (amount_ubbn + gas_fee):
        print(f"❌ Skipping {sender_addr} - insufficient BBN (has {balance / 1_000_000:.6f})")
        log_tx(sender_addr, recipient, amount_bbn, "Skipped: Low Balance")
        return

    # Retry logic
    for attempt in range(1, 4):
        try:
            msg = MsgSend(
                from_address=sender_addr,
                to_address=recipient,
                amount=[Coin(denom="ubbn", amount=str(amount_ubbn))]
            )

            tx = Transaction()
            tx.add_message(msg)
            tx = tx.with_sender(sender_addr)
            tx = tx.with_chain_id(CHAIN_ID)
            tx = tx.with_fee(gas=gas_limit, amount=gas_fee)
            tx_signed = tx.sign(sender_wallet)

            tx_resp = client.send_transaction(tx_signed)
            print(f"✅ Sent {amount_bbn} BBN from {sender_addr} to {recipient}")
            log_tx(sender_addr, recipient, amount_bbn, "Success", tx_resp.tx_hash)
            break
        except Exception as e:
            print(f"⚠️ Attempt {attempt} failed for {sender_addr} → {recipient}: {str(e)}")
            if attempt == 3:
                log_tx(sender_addr, recipient, amount_bbn, "Failed after 3 retries", str(e))
            else:
                time.sleep(5)

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
        print("❌ Invalid amount entered.")
        return

    if mode == "1":
        recipients = load_recipients()
        sender_wallet = LocalWallet.from_mnemonic(MNEMONICS[0], prefix="bbn")
        for recipient in recipients:
            send_tokens(sender_wallet, recipient, amount)

    elif mode == "2":
        recipient = input("🎯 Enter the recipient wallet address: ").strip()
        for mnemonic in MNEMONICS:
            wallet = LocalWallet.from_mnemonic(mnemonic, prefix="bbn")
            send_tokens(wallet, recipient, amount)
    else:
        print("❌ Invalid mode")

if __name__ == "__main__":
    main()
