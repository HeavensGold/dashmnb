import sys, os
sys.path.append( os.path.join( os.path.dirname(__file__), '..' ) )
sys.path.append( os.path.join( os.path.dirname(__file__), '..', 'dashlib' ) )

from config import *
from mnb_misc import *
from mnb_rpc import *
from mnb_mnconf import *
from mnb_bip32 import *


def print_balance(mn_config):
    print('[masternodes balance]')
    print('alias\tcnt\tbalance')

    for m in sorted(list(mn_config.keys())):
        alias   = mn_config[m].get('alias')
        unspent = mn_config[m].get('unspent')
        cnt     = len(unspent)

        amount_total = 1000
        for x in unspent:
            amount = x.get('amount', 0)
            amount_total += amount

        print(alias + '\t' + str(cnt) + '\t' + str(amount_total))

    print()


def get_unspent_txs(mnconfig, access):
    collateral_address   = mnconfig.get('collateral_address')
    collateral_txidtxidn = mnconfig.get('collateral_txidtxidn')

    try:
        listunspent = access.listunspent(min_conf, 999999999, [collateral_address])
    
    except Exception as e:
        print(e.args)
        sys.exit("\n\nDash-QT or dashd running ?\n")

    unspent_mine = []
    for m in listunspent:
        unspent_txidtxidn = get_txidtxidn(m['txid'], m['vout'])
        unspent_amount    = m['amount']

        if (unspent_txidtxidn != collateral_txidtxidn) and (unspent_amount < max_amounts):
            unspent_mine.append(m)    


    txs = []
    for x in unspent_mine:
        if x.get('address') == collateral_address:
            tx = {
                "amount": x.get('amount'),
                "txid": x.get('txid'),
                "vout": x.get('vout')
            }
            txs.append(tx)

    sublist = [txs[i:i+max_unspent] for i  in range(0, len(txs), max_unspent)]

    return unspent_mine, sublist

def make_inputs_for_keepkey(tx, receiving_address, collateral_spath, client):
    import binascii
    from decimal import Decimal

    import keepkeylib.messages_pb2 as proto
    import keepkeylib.types_pb2 as proto_types    
    from keepkeylib import tx_api
    from keepkeylib.tx_api import TXAPIDashTestnet   

    tx_api.rpcuser = rpcuser
    tx_api.rpcpassword = rpcpassword
    tx_api.rpcbindip = rpcbindip
    tx_api.rpcport = rpcport
    
    client.set_tx_api(TXAPIDashTestnet())

    inputs = []
    outputs = []
    amount_total = 0
    purpose, coin_type, account, change = chain_path()

    if collateral_spath == None or receiving_address == None:
        sys.exit('make_inputs_for_keepkey receiving_address / collateral_spath : Should not None')

    # make input
    for x in tx:
        amount = x.get('amount', None)
        txid   = x.get('txid', None)
        vout   = x.get('vout', None)

        if amount == None or txid == None or vout == None:
            sys.exit('make_inputs_for_keepkey amount / txid / vout : Should not None')

        amount_total += amount
        inputs.append( proto_types.TxInputType(address_n=[purpose | 0x80000000, coin_type | 0x80000000, account | 0x80000000, change, int(collateral_spath)],
                                                    prev_hash=binascii.unhexlify(txid),
                                                    prev_index=vout) )

    txsizefee = round((len(inputs) * 148 + 33 - 10) / 1000) * min_fee

    # make output based on inputs
    outputs.append( proto_types.TxOutputType(address=receiving_address,
                      amount=int(amount_total * 100000000) - txsizefee,
                      script_type=proto_types.PAYTOADDRESS,
                      ) )


    feetohuman = round(Decimal(txsizefee / 1e8), 4)
    print('send %s, %s txs to %s with fee of %s : total amount : %s' % (amount_total - feetohuman, len(tx), receiving_address, feetohuman, amount_total))
    
    try:
        (signatures, serialized_tx) = client.sign_tx(coin_name, inputs, outputs)

    except KeyboardInterrupt:
        client.close()
        sys.exit()

    return serialized_tx.hex()

def make_txs_for_keepkey(mnconfig, client):  
    
    txs = mnconfig.get('txs', None)
    collateral_spath = mnconfig.get('collateral_spath', None)
    receiving_address = mnconfig.get('receiving_address', None)

    if collateral_spath == None or receiving_address == None:
        sys.exit('make_inputs_for_keepkey receiving_address / collateral_spath : Should not None')

    serialized_txs = []
    if txs != None:
        for tx in txs:
            if (len(tx)) > min_unspent:
                serialized_tx = make_inputs_for_keepkey(tx, receiving_address, collateral_spath, client)
                serialized_txs.append(serialized_tx)

    return serialized_txs


# end