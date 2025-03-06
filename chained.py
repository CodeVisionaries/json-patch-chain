import argparse
import json
import os
import sys
import jsonpatch
import hashlib
from datetime import datetime
from typing import Callable, Optional
from random import randint
from pathlib import Path

try:
    import ENDFtk as tk
except Exception:
    print(
        "You need to install ENDFtk to use this :(, please compile and install it locally"
    )
    sys.exit(1)


def load_json(filename: str | Path) -> dict:
    """Load data from the specified file."""
    if os.path.exists(filename):
        with open(filename, "r") as file:
            return json.load(file)
    return {}


def save_json(filename: str | Path, data: dict) -> None:
    """Save data to the specified file."""
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)


def _now() -> datetime:
    return datetime.now()


def _hashfunc(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()


def load_tape(filename: str | Path) -> tuple[bool, tk.tree.Tape]:
    tape = tk.tree.Tape.from_file(str(filename))
    try:
        for material in tape.materials:
            material.parse()
    except Exception:
        return (False, None)
    return (True, tape)


def create_data_block_from_tape(tape: tk.tree.Tape) -> dict:
    # assumes one material per tape for now
    assert len(tape.materials) == 1
    material = tape.materials.front()
    parsed_material = material.parse()
    mf1 = parsed_material.file(1)
    details = mf1.sections.front()
    zai = details.ZA * 10 + details.LISO
    # use mf3, mt1 for test purposes
    energies = xs = []
    if parsed_material.has_section(3, 1):
        mf3_mt1 = parsed_material.section(3, 1)
        energies = mf3_mt1.energies.to_list()
        xs = mf3_mt1.cross_sections.to_list()

    return {
        "zai": zai,
        "mf3": {
            "mt1": {
                "energies": energies,
                "xs": xs,
            }
        },
    }


class Block:
    def __init__(
        self,
        index: int,
        patch: dict,
        previous_hash: str,
        timestamp: Optional[None | datetime] = None,
        difficulty: Optional[int] = 1,
    ):
        self.index = index
        self.patch = patch
        self.timestamp = _now() if timestamp is None else timestamp
        self.previous_hash = previous_hash
        self.difficulty = difficulty

        self.hashresult = None
        self.nonce = None

    def do_hash(self, workvalue: int) -> str:
        props = (
            (
                self.index,
                lambda x: str(x),
            ),
            (
                self.timestamp,
                lambda x: str(x),
            ),
            (
                self.patch,
                lambda x: json.dumps(x, sort_keys=True),
            ),
            (
                self.previous_hash,
                lambda x: str(x),
            ),
            (
                workvalue,
                lambda x: str(x),
            ),
        )
        dstr = "".join([fn(p) for p, fn in props])
        return _hashfunc(dstr)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp.isoformat(),
            "previous_hash": self.previous_hash,
            "block_hash": self.hashresult,
            "patch": self.patch,
            "workvalue": self.nonce,
            "difficulty": self.difficulty,
        }

    @staticmethod
    def from_dict(data: dict) -> "Block":
        block = Block(
            data["index"],
            data["patch"],
            data["previous_hash"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            difficulty=data["difficulty"],
        )
        block.hashresult = data["block_hash"]
        block.nonce = data["workvalue"]
        return block

    def check(self, hashresult: str) -> bool:
        return int(hashresult, 16) < 2 ** (256 - self.difficulty)

    def do_work(self) -> tuple[int, str]:
        """
        In the case of nuclear data, the nonce doesn't make much sense.
        """
        compare_value = 2 ** (256 - self.difficulty)

        def _check_hash_quick(hashresult: str) -> bool:
            return int(hashresult, 16) < compare_value

        nonce = randint(0, 2**32)
        hashresult = self.do_hash(nonce)
        while _check_hash_quick(hashresult) is False:
            nonce += 1
            hashresult = self.do_hash(nonce)

        self.hashresult = hashresult
        self.nonce = nonce

        return (
            nonce,
            hashresult,
        )

    def verify(
        self,
    ) -> bool:
        """workvalue is the cnonce"""
        if self.nonce is None:
            return False

        hashresult = self.do_hash(self.nonce)

        return self.check(hashresult)



_BLOCKCHAIN_FILE = "blockchain.json"

class Blockchain:
    def __init__(self):
        if Path(_BLOCKCHAIN_FILE).is_file():
            raw = load_json(_BLOCKCHAIN_FILE)
            self.from_dict(raw)
        else:
            self._chain = [self._create_genesis_block()]

        self._apply_patches()

    def _apply_patches(self) -> "Blockchain":
        self._patched_data = {}
        for block in self._chain:
            patch = jsonpatch.JsonPatch(block.patch)
            self._patched_data = patch.apply(self._patched_data)

    # the serailization will be really slow for large chains
    # this is far from optimal but for a POC it should be fine
    def from_dict(self, chain: dict) -> "Blockchain":
        self._chain = []
        for data in chain:
            self._chain.append(Block.from_dict(data))
        return self

    # the serailization will be really slow for large chains
    # this is far from optimal but for a POC it should be fine
    def to_dict(self) -> dict:
        chain_data = []
        for block in self._chain:
            assert isinstance(block, Block)
            chain_data.append(block.to_dict())
        return chain_data

    def _create_genesis_block(self) -> Block:
        block = Block(0, {}, '', difficulty=16)
        block.do_work()
        return block

    def append(self, data: dict, difficulty: int) -> "Blockchain":
        previous_block = self._chain[-1]
        index = previous_block.index + 1
        previous_hash = previous_block.hashresult
        # Create a JSON patch to track changes
        patch = jsonpatch.make_patch(self._patched_data, data)
        new_block = Block(index, patch.patch, previous_hash, difficulty=difficulty)
        _ = new_block.do_work()
        self._chain.append(new_block)
        save_json(_BLOCKCHAIN_FILE, self.to_dict())
        return self

    def is_valid(self) -> bool:
        for block in self._chain:
            if not block.verify():
                return False

        return True

    def iterate(self, func: Callable[[Block], None]) -> None:
        for block in self._chain:
            func(block)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("endf_file")
    args = parser.parse_args()

    endf_file = args.endf_file

    is_valid, tape = load_tape(endf_file)
    if not is_valid:
        raise RuntimeError("Not a valid ENDF file.")
    tape_data = create_data_block_from_tape(tape)

    chain = Blockchain()
    print("Processing chain....")
    is_valid = chain.is_valid()
    print(f"Chain is {'' if is_valid else 'not'} valid")

    if not is_valid:
        sys.exit(1)

    print("Adding patch...")
    chain.append(tape_data, difficulty=8)
    print("Checking chain....")
    is_valid = chain.is_valid()
    print(f"Chain is {'' if is_valid else 'not'} valid")
    if not is_valid:
        sys.exit(1)


if __name__ == "__main__":
    main()
