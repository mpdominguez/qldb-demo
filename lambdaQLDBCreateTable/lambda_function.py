import os
import json
import boto3
import amazon.ion.simpleion as ion
import ionhash
from hashlib import sha256
from array import array

QLDBLEDGER = os.environ['QLDBLedger']

def lambda_handler(event, context):
    client = boto3.client('qldb-session')

    ledger_name = QLDBLEDGER
    response = client.send_command(
        StartSession={
            'LedgerName': ledger_name
        },
    )

    session_token = response['StartSession']['SessionToken']

    response = client.send_command(
        SessionToken=session_token,

        StartTransaction={}
    )
    transaction_id = response['StartTransaction']['TransactionId']


    statement = 'CREATE TABLE transactions'

    client.send_command(
        SessionToken=session_token,
        ExecuteStatement={
            'TransactionId': transaction_id,
            'Statement': statement,
        },
    )

    def to_qldb_hash(value):
        value = ion.loads(ion.dumps(value))
        ion_hash = value.ion_hash('SHA256')
        return ion_hash


    def hash_comparator(h1, h2):
        h1_array = array('b', h1)
        h2_array = array('b', h2)

        if len(h1) != 32 or len(h2) != 32:
            raise ValueError("Invalid hash")

        for i in range(len(h1_array) - 1, -1, -1):
            difference = h1_array[i] - h2_array[i]
            if difference != 0:
                return difference
        return 0


    def join_hashes_pair_wise(h1, h2):
        if len(h1) == 0:
            return h2

        if len(h2) == 0:
            return h1

        if hash_comparator(h1, h2) < 0:
            concatenated = h1 + h2
        else:
            concatenated = h2 + h1
        return concatenated

    def create_commit_digest(statement, transaction_id):
        concatenated = join_hashes_pair_wise(to_qldb_hash(statement), to_qldb_hash(transaction_id))
        new_hash_lib = sha256()
        new_hash_lib.update(concatenated)
        return new_hash_lib.digest()

    commit_digest = create_commit_digest(statement, transaction_id)
    response = client.send_command(
        SessionToken=session_token,

        CommitTransaction={
            'TransactionId': transaction_id,
            'CommitDigest': commit_digest
        },
    )

    client.send_command(
        SessionToken=session_token,

        EndSession={},
    )
    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps('Table transactions created in QLDB Ledger')
    }
