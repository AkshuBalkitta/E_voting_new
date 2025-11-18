from hashlib import sha256
import json
import time
import os

from flask import Flask, request
import requests
from cryptography.fernet import Fernet

# -------------------- CONFIG --------------------
FERNET_KEY = b'V0Xc2q1sN6h3gQ9tY2k7mZxU8aP1bR4vQeK5yJtLq0s='
fernet = Fernet(FERNET_KEY)

PUBLIC_CHAIN_FILE = "public_chain.json"
COUNTING_CHAIN_FILE = "counting_chain.json"
# ------------------------------------------------

def encrypt_party(party_name: str) -> str:
    return fernet.encrypt(party_name.encode()).decode()


class Block:
    def __init__(self, index, transactions, timestamp, previous_hash, nonce=0):
        self.index = index
        self.transactions = transactions
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.nonce = nonce

    def compute_hash(self):
        block_string = json.dumps(self.__dict__, sort_keys=True)
        return sha256(block_string.encode()).hexdigest()


class Blockchain:
    difficulty = 2

    def __init__(self):
        self.unconfirmed_transactions = []
        self.chain = []

    def create_genesis_block(self):
        genesis_block = Block(0, [], 0, "0")
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)

    @property
    def last_block(self):
        return self.chain[-1]

    def add_block(self, block, proof):
        previous_hash = self.last_block.hash
        if previous_hash != block.previous_hash:
            return False
        if not Blockchain.is_valid_proof(block, proof):
            return False
        block.hash = proof
        self.chain.append(block)
        return True

    @staticmethod
    def proof_of_work(block):
        block.nonce = 0
        computed_hash = block.compute_hash()
        while not computed_hash.startswith('0' * Blockchain.difficulty):
            block.nonce += 1
            computed_hash = block.compute_hash()
        return computed_hash

    def add_new_transaction(self, transaction):
        self.unconfirmed_transactions.append(transaction)

    @classmethod
    def is_valid_proof(cls, block, block_hash):
        return (block_hash.startswith('0' * Blockchain.difficulty) and
                block_hash == block.compute_hash())

    @classmethod
    def check_chain_validity(cls, chain):
        previous_hash = "0"
        for block in chain:
            block_hash = block.hash
            delattr(block, "hash")
            if not cls.is_valid_proof(block, block_hash) or previous_hash != block.previous_hash:
                return False
            block.hash, previous_hash = block_hash, block_hash
        return True

    def mine(self):
        if not self.unconfirmed_transactions:
            return False
        last_block = self.last_block
        new_block = Block(
            index=last_block.index + 1,
            transactions=self.unconfirmed_transactions,
            timestamp=time.time(),
            previous_hash=last_block.hash
        )
        proof = self.proof_of_work(new_block)
        self.add_block(new_block, proof)
        self.unconfirmed_transactions = []
        return True

    # ---------- PERSISTENCE METHODS ----------
    def save_chain(self, filename):
        data = {
            "chain": [block.__dict__ for block in self.chain],
            "unconfirmed_transactions": self.unconfirmed_transactions
        }
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)

    def load_chain(self, filename):
        if os.path.exists(filename):
            with open(filename, "r") as f:
                data = json.load(f)
            self.chain = []
            for blk in data.get("chain", []):
                block = Block(
                    blk["index"],
                    blk.get("transactions", []),
                    blk.get("timestamp", 0),
                    blk.get("previous_hash", ""),
                    blk.get("nonce", 0)
                )
                block.hash = blk.get("hash")
                self.chain.append(block)
            self.unconfirmed_transactions = data.get("unconfirmed_transactions", [])
# -------------------------------------------

app = Flask(__name__)

# ---------- two blockchains ------------------
public_blockchain = Blockchain()
if os.path.exists(PUBLIC_CHAIN_FILE):
    public_blockchain.load_chain(PUBLIC_CHAIN_FILE)
else:
    public_blockchain.create_genesis_block()

counting_blockchain = Blockchain()
if os.path.exists(COUNTING_CHAIN_FILE):
    counting_blockchain.load_chain(COUNTING_CHAIN_FILE)
else:
    counting_blockchain.create_genesis_block()
# -------------------------------------------

peers = set()


@app.route('/new_transaction', methods=['POST'])
def new_transaction():
    tx_data = request.get_json()
    required_fields = ["voter_id", "party"]
    for field in required_fields:
        if not tx_data.get(field):
            return "Invalid transaction data", 404

    ts = time.time()
    public_tx = {
        "voter_id": tx_data["voter_id"],
        "party": encrypt_party(tx_data["party"]),
        "timestamp": ts
    }
    counting_tx = {
        "voter_id": tx_data["voter_id"],
        "party": tx_data["party"],
        "timestamp": ts
    }

    public_blockchain.add_new_transaction(public_tx)
    counting_blockchain.add_new_transaction(counting_tx)

    # Save immediately to persist unconfirmed tx
    public_blockchain.save_chain(PUBLIC_CHAIN_FILE)
    counting_blockchain.save_chain(COUNTING_CHAIN_FILE)

    return "Success", 201


@app.route('/chain', methods=['GET'])
def get_chain():
    chain_data = [block.__dict__ for block in public_blockchain.chain]
    return json.dumps({
        "length": len(chain_data),
        "chain": chain_data,
        "peers": list(peers)
    })


@app.route('/mine', methods=['GET'])
def mine_unconfirmed_transactions():
    result_public = public_blockchain.mine()
    result_counting = counting_blockchain.mine()

    if not result_public and not result_counting:
        return "No transactions to mine"

    # save chains after mining
    public_blockchain.save_chain(PUBLIC_CHAIN_FILE)
    counting_blockchain.save_chain(COUNTING_CHAIN_FILE)

    chain_length = len(public_blockchain.chain)
    consensus()
    if chain_length == len(public_blockchain.chain):
        announce_new_block(public_blockchain.last_block)

    return f"Public Block #{public_blockchain.last_block.index} mined. Counting chain synced."


@app.route('/results_count', methods=['GET'])
def results_count():
    counts = {}
    for block in counting_blockchain.chain:
        for tx in block.transactions:
            party = tx.get("party")
            if not party:
                continue
            counts[party] = counts.get(party, 0) + 1
    return json.dumps(counts)


# --------------------- PEER METHODS ---------------------
@app.route('/register_node', methods=['POST'])
def register_new_peers():
    node_address = request.get_json()["node_address"]
    if not node_address:
        return "Invalid data", 400
    peers.add(node_address)
    return get_chain()


@app.route('/register_with', methods=['POST'])
def register_with_existing_node():
    node_address = request.get_json()["node_address"]
    if not node_address:
        return "Invalid data", 400

    data = {"node_address": request.host_url}
    headers = {'Content-Type': "application/json"}
    response = requests.post(node_address + "/register_node",
                             data=json.dumps(data), headers=headers)

    if response.status_code == 200:
        global public_blockchain
        global peers
        chain_dump = response.json()['chain']
        public_blockchain = create_chain_from_dump(chain_dump)
        peers.update(response.json()['peers'])
        return "Registration successful", 200
    else:
        return response.content, response.status_code


def create_chain_from_dump(chain_dump):
    generated_blockchain = Blockchain()
    generated_blockchain.create_genesis_block()
    for idx, block_data in enumerate(chain_dump):
        if idx == 0:
            continue
        block = Block(block_data["index"],
                      block_data.get("transactions", []),
                      block_data.get("timestamp", 0),
                      block_data.get("previous_hash", ""),
                      block_data.get("nonce", 0))
        proof = block_data.get('hash')
        added = generated_blockchain.add_block(block, proof)
        if not added:
            raise Exception("The chain dump is tampered!!")
    return generated_blockchain


@app.route('/add_block', methods=['POST'])
def verify_and_add_block():
    block_data = request.get_json()
    block = Block(block_data["index"],
                  block_data.get("transactions", []),
                  block_data.get("timestamp", 0),
                  block_data.get("previous_hash", ""),
                  block_data.get("nonce", 0))
    proof = block_data.get('hash')
    added = public_blockchain.add_block(block, proof)
    if not added:
        return "The block was discarded by the node", 400
    return "Block added to the public chain", 201


@app.route('/pending_tx')
def get_pending_tx():
    return json.dumps(public_blockchain.unconfirmed_transactions)


def consensus():
    global public_blockchain
    longest_chain = None
    current_len = len(public_blockchain.chain)

    for node in peers:
        try:
            response = requests.get(f'{node}chain', timeout=3)
            response.raise_for_status()
            length = response.json().get('length', 0)
            chain = response.json().get('chain', [])
            temp_chain = []
            for blk in chain:
                b = Block(blk.get('index'), blk.get('transactions', []), blk.get('timestamp', 0),
                          blk.get('previous_hash', ''), blk.get('nonce', 0))
                b.hash = blk.get('hash')
                temp_chain.append(b)
            if length > current_len and Blockchain.check_chain_validity(temp_chain):
                current_len = length
                longest_chain = chain
        except Exception as e:
            print("consensus: node unreachable or invalid data:", e)
            continue

    if longest_chain:
        public_blockchain = create_chain_from_dump(longest_chain)
        public_blockchain.save_chain(PUBLIC_CHAIN_FILE)
        return True
    return False


def announce_new_block(block):
    for peer in peers:
        url = "{}add_block".format(peer)
        headers = {'Content-Type': "application/json"}
        try:
            requests.post(url,
                          data=json.dumps(block.__dict__, sort_keys=True),
                          headers=headers, timeout=3)
        except Exception as e:
            print("announce_new_block failed for peer", peer, e)


if __name__ == '__main__':
    app.run(debug=True, port=8000)
