import hashlib
import json
import time

class Block:
    def __init__(self, index, previous_hash, timestamp, data, hash):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.data = data
        self.hash = hash

def create_genesis_block():
    return Block(0, "0", time.time(), "Genesis Block", calculate_hash(0, "0", time.time(), "Genesis Block"))

def calculate_hash(index, previous_hash, timestamp, data):
    block_data = f'{index}{previous_hash}{timestamp}{data}'
    return hashlib.sha256(block_data.encode('utf-8')).hexdigest()

def create_new_block(previous_block, data):
    index = previous_block.index + 1
    timestamp = time.time()
    hash = calculate_hash(index, previous_block.hash, timestamp, data)
    return Block(index, previous_block.hash, timestamp, data, hash)

def is_chain_valid(chain):
    for i in range(1, len(chain)):
        current_block = chain[i]
        previous_block = chain[i - 1]

        if current_block.hash != calculate_hash(current_block.index, current_block.previous_hash, current_block.timestamp, current_block.data):
            return False

        if current_block.previous_hash != previous_block.hash:
            return False

    return True
