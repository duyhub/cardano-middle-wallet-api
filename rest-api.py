from quart import Quart
from quart import request
from transactions import *

app = Quart(__name__)


@app.route('/v0/version', methods=['GET'])
async def get_version():
    response = {'version': 'v0.97',
                'dd/mm/yy': '21/1/22',
                'Release note': "add new v1/trade/ endpoints for non-stake address trading system"}
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/nodestatus', methods=['GET'])
async def node_status_handler(network=NETWORK):
    # Query tip
    tip_parameters = [CARDANO_CLI_PATH, 'query', 'tip']
    if network == 'mainnet':
        tip_parameters += ['--mainnet']
    else:
        tip_parameters += ['--testnet-magic', TESTNET_MAGIC]

    # Set status
    output = run_command(tip_parameters, _env=my_env)
    if type(output) is subprocess.CalledProcessError:
        status = {'status': 'offline'}
    else:
        output = json.loads(output.decode('utf-8'))
        if float(output["syncProgress"]) == 100:
            status = {'status': 'online', 'tip': output}
        else:
            status = {'status': 'syncing', 'tip': output}
    status['network'] = network
    return json.dumps(status), {'Content-Type': 'application/json'}


@app.route('/v0/createwallet', methods=['GET'])
# Create a wallet
async def create_wallet_handler():
    response = create_wallet_address()
    return response, {'Content-Type': 'application/json'}


@app.route('/v0/wallets/<string:stake_address>/', methods=['GET'])
# Get ADA and assets
async def get_wallet_detail_handler(stake_address):
    return json.dumps(get_balance_by_stake_address(stake_address)), {'Content-Type': 'application/json'}


@app.route('/v0/addresses/<string:address>/utxos', methods=['GET'])
# Query utxos available in the address
async def query_utxo_handler(address):
    utxo_list = query_utxos(address)
    print(f'query_utxo_handler: {utxo_list}')
    response = []
    for utxo in utxo_list:
        temp = {
            'tx_hash': utxo[0],
            'tx_index': utxo[1],
            'amount': []
        }
        _dict = {}
        datum_hash = None
        pairs = [(i + 2, i + 3) for i in range(0, len(utxo) - 3, 3)]
        for pair in pairs:
            unit_pos = pair[1]
            quantity_pos = pair[0]
            unit = utxo[unit_pos]
            quantity = utxo[quantity_pos]
            if quantity == 'TxOutDatumHash':
                datum_hash = utxo[-1].strip('"')
                break
            if unit in _dict:
                _dict[unit] += int(quantity)
            else:
                _dict[unit] = int(quantity)
        amount = []
        for key in _dict:
            amount.append({
                'unit': key,
                'quantity': str(_dict[key])
            })
        temp['amount'] = amount
        temp['datum_hash'] = datum_hash
        response.append(temp)
    print(f'query_utxo_handler response: {response}')
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/stake-addresses/<string:stake_address>/utxos', methods=['GET'])
# Query utxos in the stake_address
async def query_utxo_by_stake_address_handler(stake_address):
    utxo_list = query_utxos_by_stake_address(stake_address)
    response = []
    for utxo in utxo_list:
        temp = {
            'tx_hash': utxo[0],
            'tx_index': utxo[1],
            'amount': []
        }
        _dict = {}
        datum_hash = None
        pairs = [(i + 2, i + 3) for i in range(0, len(utxo) - 3, 3)]
        for pair in pairs:
            unit_pos = pair[1]
            quantity_pos = pair[0]
            unit = utxo[unit_pos]
            quantity = utxo[quantity_pos]
            if quantity == 'TxOutDatumHash':
                datum_hash = utxo[-1].strip('"')
                break
            if unit in _dict:
                _dict[unit] += int(quantity)
            else:
                _dict[unit] = int(quantity)
        amount = []
        for key in _dict:
            amount.append({
                'unit': key,
                'quantity': str(_dict[key])
            })
        temp['amount'] = amount
        temp['datum_hash'] = datum_hash
        response.append(temp)
    return response, {'Content-Type': 'application/json'}


@app.route('/v0/addresses/<string:address>/balance', methods=['GET'])
# Query total ADA and assets in the payment address
async def query_balance_handler(address):
    utxo_list = query_utxos(address)
    total_ada = 0
    asset_list = []
    temp_dict = {}
    for utxo in utxo_list:
        total_ada += int(utxo[2])
        if len(utxo) > 6:
            if utxo[6] in temp_dict:
                temp_dict[utxo[6]] += int(utxo[5])
            else:
                temp_dict[utxo[6]] = int(utxo[5])
    for key in temp_dict:
        asset_list.append({'unit': key, 'quantity': str(temp_dict[key])})
    response = {'lovelace': str(total_ada), 'asset': asset_list}
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/addresses/<string:address>/stake_address', methods=['GET'])
# Get stake address from address
async def get_stake_address_handler(address):
    stake_address = get_stake_address(address)
    response = {'stake_address': stake_address}
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/trade/return', methods=['POST'])
# Description: Return all registered ADA, assets back to registered owners
# Note: stake address for buyers and sellers applies
async def trade_return_all_utxos_handler():
    # Get data
    data = await request.get_json()
    address = data['address']
    signing_key = data['signing_key']
    buy_listing = data['buy']
    buy_quantity = str(buy_listing['quantity'])
    sell_listing = data['sell']
    sell_quantity = str(sell_listing['quantity'])
    # market_address = data['market_address']

    # Write signing key to file
    if not os.path.isdir('request'):
        os.makedirs('request')

    _id = get_unique_id()
    signing_key_path = f'request/payment_{_id}.skey'
    with open(signing_key_path, 'w') as file:
        json.dump(signing_key, file)

    # Make a directory to store transaction processing file
    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    # Get stake address list from buyer and seller's account
    stake_list = []
    buyer_stake_list = []
    seller_stake_list = []
    for stake_address in data['buyer_stake_list']:
        buyer_stake_list.append(stake_address['stake_address'])
        stake_list.append(stake_address['stake_address'])
    for stake_address in data['seller_stake_list']:
        seller_stake_list.append(stake_address['stake_address'])
        stake_list.append(stake_address['stake_address'])

    # Declare variables
    buyer_check = False
    seller_check = False

    # Query utxos in address
    utxo_list = query_utxos(address)

    buyer_address, ada_tx, seller_address, asset_tx, utxo_mark, from_address = check_buyer_and_seller(utxo_list,
                                                                                                      buyer_stake_list,
                                                                                                      seller_stake_list,
                                                                                                      buy_listing,
                                                                                                      sell_listing)
    if buyer_address != '':
        buyer_check = True
    if seller_address != '':
        seller_check = True

    # Choose network
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    signed_path = ''
    _id = get_unique_id()
    draft_path = f'transactions/tx_{_id}.draft'

    # Build the transaction
    # tx-in
    build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build']
    for i, utxo in enumerate(utxo_list):
        if utxo_mark[i] == 1:
            build_parameters += ['--tx-in', f'{utxo[0]}#{utxo[1]}']

    # If tx-in is empty, return fail
    response = {}
    if len(build_parameters) <= 3:
        response['txids'] = []
        return json.dumps(response), {'Content-Type': 'application/json'}

    if buyer_check is True and seller_check is False:
        for i, utxo in enumerate(utxo_list):
            if utxo[0] == ada_tx:
                continue
            if utxo_mark[i] == 1:
                if len(utxo) <= 6:
                    build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}']
                else:
                    build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}'
                                                     f'+{utxo[5]} {utxo[6]}']

        # The buyer covers the refund's network fee when session fails
        build_parameters += ['--change-address', buyer_address]

    elif buyer_check is False and seller_check is False:
        cover_utxo_address = ''
        for i, utxo in enumerate(utxo_list):
            if utxo_mark[i] == 1:
                if len(utxo) <= 6 and int(utxo[2]) >= 2000000 and cover_utxo_address == '':
                    cover_utxo_address = from_address[i]
                    continue
                if len(utxo) <= 6:
                    build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}']
                else:
                    build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}'
                                                     f'+{utxo[5]} {utxo[6]}']

        if cover_utxo_address == '':
            print('trade_return_all_utxos_handler: Not enough fund to cover network fee. Need at least 2 ADA')
            response['txids'] = []
            # Clean transaction files
            try:
                os.remove(signing_key_path)
                os.remove(draft_path)
            except FileNotFoundError as e:
                print(f'trade_return_all_utxos_handler: {e.errno}')

            return json.dumps(response), {'Content-Type': 'application/json'}
        # if cover_utxo_address == '':
        #     raise ValueError(f'trade_return_all_utxos_handler: Not enough fund to cover network fee.'
        #                      f'Need at least 1 ADA-only utxo containing equal or more than 2 ADA.')

        build_parameters += ['--change-address', cover_utxo_address]
    build_parameters += net
    build_parameters += ['--out-file', draft_path, '--alonzo-era']

    # Build transaction
    output = run_command(build_parameters, my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output

    # Sign the transaction draft
    signed_path = f'transactions/tx_{_id}.signed'
    sign_parameters = [CARDANO_CLI_PATH, 'transaction', 'sign',
                       '--tx-body-file', draft_path,
                       '--signing-key-file', signing_key_path]
    sign_parameters += net
    sign_parameters += ['--out-file', signed_path]

    output = run_command(sign_parameters, my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output

    # Submit the transaction
    submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                         '--tx-file', signed_path]
    submit_parameters += net

    result = run_command(submit_parameters, _env=my_env)
    if type(result) is subprocess.CalledProcessError:
        raise result

    print(result.decode('utf-8'))

    # Record the txid
    txid_parameters = [CARDANO_CLI_PATH, 'transaction', 'txid', '--tx-file', signed_path]

    txid = run_command(txid_parameters, my_env)
    if type(txid) is subprocess.CalledProcessError:
        raise txid

    response['txids'] = [{'txid': txid.decode('utf-8').strip('\n')}]

    # Clean transaction files
    try:
        os.remove(signing_key_path)
        os.remove(signed_path)
        os.remove(draft_path)
    except FileNotFoundError as e:
        print(f'trade_return_all_utxos_handler: {e.errno}')

    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v1/trade/return', methods=['POST'])
# Return all utxos regardless of coming from registered addresses or unregistered addresses
async def v1_trade_return_all_utxos_handler():
    data = await request.get_json()
    address = data['address']
    signing_key = data['signing_key']

    # Make directory
    if not os.path.isdir('request'):
        os.makedirs('request')

    # Write signing key to file
    _id = get_unique_id()
    signing_key_path = f'request/payment_{_id}.skey'
    with open(signing_key_path, 'w') as file:
        json.dump(signing_key, file)

    # Return utxos
    txid = return_all_utxos(address, signing_key_path)
    if len(txid) > 0:
        response = {'status': 'success'}
    else:
        response = {'status': 'failed'}
    response['txids'] = txid

    try:
        os.remove(signing_key_path)
    except FileNotFoundError as e:
        print(f'return_all_utxos_handler: {e.errno}')
        raise ValueError(f'return_all_utxos_handler: {e.errno}')

    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/trade/finalize', methods=['POST'])
# Send asset to buyer, ADA to seller and service fee to market account if all assets and ADA are confirmed
# Note: Only registered utxos are processed, unregistered utxos stay in the middle wallet
async def trade_finalize_handler():
    # Get data
    data = await request.get_json()
    address = data['address']
    signing_key = data['signing_key']
    buy_listing = data['buy']
    buy_quantity = str(buy_listing['quantity'])
    sell_listing = data['sell']
    sell_quantity = str(sell_listing['quantity'])
    market_address = data['market_address']

    # Write signing key to file
    if not os.path.isdir('request'):
        os.makedirs('request')

    _id = get_unique_id()
    signing_key_path = f'request/payment_{_id}.skey'
    with open(signing_key_path, 'w') as file:
        json.dump(signing_key, file)

    # Make a directory to store transaction processing file
    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    # Get stake address list from buyer and seller's account
    stake_list = []
    buyer_stake_list = []
    seller_stake_list = []
    for stake_address in data['buyer_stake_list']:
        buyer_stake_list.append(stake_address['stake_address'])
        stake_list.append(stake_address['stake_address'])
    for stake_address in data['seller_stake_list']:
        seller_stake_list.append(stake_address['stake_address'])
        stake_list.append(stake_address['stake_address'])

    # Declare variables
    buyer_check = False
    seller_check = False

    # Query utxos in address
    utxo_list = query_utxos(address)

    buyer_address, ada_tx, seller_address, asset_tx, utxo_mark, from_address = check_buyer_and_seller(utxo_list,
                                                                                                      buyer_stake_list,
                                                                                                      seller_stake_list,
                                                                                                      buy_listing,
                                                                                                      sell_listing)
    if buyer_address != '':
        buyer_check = True
    if seller_address != '':
        seller_check = True

    # if buyer_utxo_count != 1 or seller_utxo_count != 1:
    #     raise ValueError('Error while determining buyer and seller address')

    # Send asset, ADA to buyer and seller if status is "verified"
    # Refund all ADA-only utxos if status is "unverified"
    response = {'status': 'failed'}
    if buyer_check is True and seller_check is True:
        response['status'] = 'success'

    # Calculate service fee
    price = int(buy_listing['quantity'])
    service_fee = int(round(price * float(data['service_rate'])))
    service_fee = max(service_fee, 1000000)
    print(f'service_fee: {service_fee}')

    # Choose network
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    _id = get_unique_id()
    draft_path = f'transactions/tx_{_id}.draft'

    # Build the transaction
    # tx-in
    build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build']
    for i, utxo in enumerate(utxo_list):
        if utxo_mark[i] == 1:
            build_parameters += ['--tx-in', f'{utxo[0]}#{utxo[1]}']

    # If tx-in is empty, return fail
    if len(build_parameters) <= 3 or buyer_check is False or seller_check is False:
        response['txids'] = []
        # Clean transaction files
        try:
            os.remove(signing_key_path)
            os.remove(draft_path)
        except FileNotFoundError as e:
            print(f'trade_finalize_handler: clean transaction failed {e.errno}')
        return json.dumps(response)

    # tx-out
    if buyer_check is True and seller_check is True:
        for i, utxo in enumerate(utxo_list):
            if utxo[0] == asset_tx:
                # Send asset to the buyer
                build_parameters += ['--tx-out', f'{buyer_address}+{utxo[2]}+{utxo[5]} {utxo[6]}']
            elif utxo[0] == ada_tx:
                continue
            else:
                if utxo_mark[i] == 1:
                    if len(utxo) <= 6:
                        build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}']
                    else:
                        build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}'
                                                         f'+{utxo[5]} {utxo[6]}']

        # Send to market address the service fee
        # If listing price <= 20 ADA or service_rate == 0, service fee is waived
        if price > int(20e6) and float(data['service_rate']) > 0:
            build_parameters += ['--tx-out', f'{market_address}+{service_fee}']

        # Send to the seller address: listing price - service fee - network fee
        build_parameters += ['--change-address', seller_address]

    build_parameters += net
    build_parameters += ['--out-file', draft_path, '--alonzo-era']

    # Build transaction
    output = run_command(build_parameters, my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output

    # Sign the transaction draft
    signed_path = f'transactions/tx_{_id}.signed'
    sign_parameters = [CARDANO_CLI_PATH, 'transaction', 'sign',
                       '--tx-body-file', draft_path,
                       '--signing-key-file', signing_key_path]
    sign_parameters += net
    sign_parameters += ['--out-file', signed_path]

    output = run_command(sign_parameters, my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output

    # Submit the transaction
    submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                         '--tx-file', signed_path]
    submit_parameters += net

    result = run_command(submit_parameters, my_env)
    if type(result) is subprocess.CalledProcessError:
        raise result

    # Record the txid
    txid_parameters = [CARDANO_CLI_PATH, 'transaction', 'txid', '--tx-file', signed_path]

    txid = run_command(txid_parameters, my_env)
    if type(txid) is subprocess.CalledProcessError:
        raise txid

    response['txids'] = [{'txid': txid.decode('utf-8').strip('\n')}]

    # Clean transaction files
    try:
        os.remove(signing_key_path)
        os.remove(signed_path)
        os.remove(draft_path)
    except FileNotFoundError as e:
        print(f'trade_finalize_handler: clean transaction files {e.errno}')

    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v1/trade/finalize', methods=['POST'])
# Send asset to buyer, ADA to seller and service fee to market account if all assets and ADA are confirmed
# All transaction is recognized
async def v1_trade_finalize_handler():
    # Get data
    data = await request.get_json()
    address = data['address']
    signing_key = data['signing_key']
    buy_listing = data['buy']
    buy_quantity = str(buy_listing['quantity'])
    sell_listing = data['sell']
    sell_quantity = str(sell_listing['quantity'])
    market_address = data['market_address']

    # Write signing key to file
    if not os.path.isdir('request'):
        os.makedirs('request')

    _id = get_unique_id()
    signing_key_path = f'request/payment_{_id}.skey'
    with open(signing_key_path, 'w') as file:
        json.dump(signing_key, file)

    # Make a directory to store transaction processing file
    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    # Declare variables
    buyer_check = False
    seller_check = False

    # Query utxos in address
    utxo_list = query_utxos(address)

    buyer_address, ada_tx, seller_address, asset_tx, from_address = check_buyer_and_seller_without_stake_address(
        utxo_list,
        buy_listing,
        sell_listing)

    if buyer_address != '':
        buyer_check = True
    if seller_address != '':
        seller_check = True

    # Send asset, ADA to buyer and seller if status is "verified"
    # Refund all ADA-only utxos if status is "unverified"
    response = {'status': 'failed'}
    if buyer_check is True and seller_check is True:
        response['status'] = 'success'

    # Calculate service fee
    price = int(buy_listing['quantity'])
    service_fee = int(round(price * float(data['service_rate'])))
    service_fee = max(service_fee, 1000000)
    print(f'service_fee: {service_fee}')

    # Choose network
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    _id = get_unique_id()
    draft_path = f'transactions/tx_{_id}.draft'

    # Build the transaction
    # tx-in
    build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build']
    for i, utxo in enumerate(utxo_list):
        build_parameters += ['--tx-in', f'{utxo[0]}#{utxo[1]}']

    # If tx-in is empty, return fail
    if len(build_parameters) <= 3 or buyer_check is False or seller_check is False:
        response['txids'] = []
        # Clean transaction files
        try:
            os.remove(signing_key_path)
            os.remove(draft_path)
        except FileNotFoundError as e:
            print(f'trade_finalize_handler: clean transaction failed {e.errno}')
        return json.dumps(response)

    # tx-out
    if buyer_check is True and seller_check is True:
        for i, utxo in enumerate(utxo_list):
            if utxo[0] == asset_tx:
                # Send asset to the buyer
                build_parameters += ['--tx-out', f'{buyer_address}+{utxo[2]}+{utxo[5]} {utxo[6]}']
            elif utxo[0] == ada_tx:
                continue
            else:
                if len(utxo) <= 6:
                    build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}']
                else:
                    build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}'
                                                     f'+{utxo[5]} {utxo[6]}']

        # Send to market address the service fee
        # If listing price <= 20 ADA or service_rate == 0, service fee is waived
        if price > int(20e6) and float(data['service_rate']) > 0:
            build_parameters += ['--tx-out', f'{market_address}+{service_fee}']

        # Send to the seller address: listing price - service fee - network fee
        build_parameters += ['--change-address', seller_address]

    build_parameters += net
    build_parameters += ['--out-file', draft_path, '--alonzo-era']

    # Build transaction
    output = run_command(build_parameters, my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output

    # Sign the transaction draft
    signed_path = f'transactions/tx_{_id}.signed'
    sign_parameters = [CARDANO_CLI_PATH, 'transaction', 'sign',
                       '--tx-body-file', draft_path,
                       '--signing-key-file', signing_key_path]
    sign_parameters += net
    sign_parameters += ['--out-file', signed_path]

    output = run_command(sign_parameters, my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output

    # Submit the transaction
    submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                         '--tx-file', signed_path]
    submit_parameters += net

    result = run_command(submit_parameters, my_env)
    if type(result) is subprocess.CalledProcessError:
        raise result

    # Record the txid
    txid_parameters = [CARDANO_CLI_PATH, 'transaction', 'txid', '--tx-file', signed_path]

    txid = run_command(txid_parameters, my_env)
    if type(txid) is subprocess.CalledProcessError:
        raise txid

    response['txids'] = [{'txid': txid.decode('utf-8').strip('\n')}]

    # Clean transaction files
    try:
        os.remove(signing_key_path)
        os.remove(signed_path)
        os.remove(draft_path)
    except FileNotFoundError as e:
        print(f'trade_finalize_handler: clean transaction files {e.errno}')

    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/trade/status', methods=['POST'])
# Check whether seller and buyer have sent their asset/ADA
async def trade_status_handler():
    # Get data
    data = await request.get_json()
    address = data['address']
    buy_listing = data['buy']
    sell_listing = data['sell']
    # buy_quantity = str(buy_listing['quantity'])
    # sell_quantity = str(sell_listing['quantity'])

    # Change stake list to list of strings for easier reading
    buyer_stake_list = []
    for stake_address in data['buyer_stake_list']:
        buyer_stake_list.append(stake_address['stake_address'])
    seller_stake_list = []
    for stake_address in data['seller_stake_list']:
        seller_stake_list.append(stake_address['stake_address'])

    # Declare variables
    utxos = []
    buyer_check = False
    seller_check = False

    # Query utxos in address
    utxo_list = query_utxos(address)

    buyer_address, ada_tx, seller_address, asset_tx, utxo_mark, from_address = check_buyer_and_seller(utxo_list,
                                                                                                      buyer_stake_list,
                                                                                                      seller_stake_list,
                                                                                                      buy_listing,
                                                                                                      sell_listing)

    if buyer_address != '':
        buyer_check = True
    if seller_address != '':
        seller_check = True

    for utxo in utxo_list:
        utxos.append({'utxo': ' '.join(utxo)})

    response = {
        'buyer_sent': buyer_check,
        'seller_sent': seller_check,
        'utxos': utxos
    }
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v1/trade/status', methods=['POST'])
# Check whether seller and buyer have sent their asset/ADA, but don't check stake address
async def v1_trade_status_handler():
    # Get data
    data = await request.get_json()
    address = data['address']
    buy_listing = data['buy']
    sell_listing = data['sell']
    # buy_quantity = str(buy_listing['quantity'])
    # sell_quantity = str(sell_listing['quantity'])

    # Declare variables
    utxos = []
    buyer_check = False
    seller_check = False

    # Query utxos in address
    utxo_list = query_utxos(address)

    buyer_address, ada_tx, seller_address, asset_tx, from_address = check_buyer_and_seller_without_stake_address(
        utxo_list,
        buy_listing,
        sell_listing)

    if buyer_address != '':
        buyer_check = True
    if seller_address != '':
        seller_check = True

    for utxo in utxo_list:
        utxos.append({'utxo': ' '.join(utxo)})

    response = {
        'buyer_sent': buyer_check,
        'seller_sent': seller_check,
        'utxos': utxos
    }
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/trade/status-blockfrost', methods=['POST'])
# Check whether seller and buyer have sent their asset/ADA
async def trade_status_blockfrost_handler():
    # Get data
    data = await request.get_json()
    address = data['address']
    buy_listing = data['buy']
    sell_listing = data['sell']
    # buy_quantity = str(buy_listing['quantity'])
    # sell_quantity = str(sell_listing['quantity'])

    # Change stake list to list of strings for easier reading
    buyer_stake_list = []
    for stake_address in data['buyer_stake_list']:
        buyer_stake_list.append(stake_address['stake_address'])
    seller_stake_list = []
    for stake_address in data['seller_stake_list']:
        seller_stake_list.append(stake_address['stake_address'])

    # Declare variables
    utxos = []
    buyer_check = False
    seller_check = False

    # Query utxos in address
    utxo_list = query_utxos_blockfrost(address)

    buyer_address, ada_tx, seller_address, asset_tx, utxo_mark, from_address = check_buyer_and_seller_blockfrost(
        utxo_list,
        buyer_stake_list,
        seller_stake_list,
        buy_listing,
        sell_listing)

    if buyer_address != '':
        buyer_check = True
    if seller_address != '':
        seller_check = True

    for utxo in utxo_list:
        utxos.append(utxo)

    response = {
        'buyer_sent': buyer_check,
        'seller_sent': seller_check,
        'utxos': utxos
    }
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v1/trade/status-blockfrost', methods=['POST'])
# Check whether seller and buyer have sent their asset/ADA, without stake address
async def v1_trade_status_blockfrost_handler():
    # Get data
    data = await request.get_json()
    address = data['address']
    buy_listing = data['buy']
    sell_listing = data['sell']

    # Change stake list to list of strings for easier reading
    buyer_stake_list = []
    for stake_address in data['buyer_stake_list']:
        buyer_stake_list.append(stake_address['stake_address'])
    seller_stake_list = []
    for stake_address in data['seller_stake_list']:
        seller_stake_list.append(stake_address['stake_address'])

    # Declare variables
    utxos = []
    buyer_check = False
    seller_check = False

    # Query utxos in address
    utxo_list = query_utxos_blockfrost(address)

    buyer_address, ada_tx, seller_address, asset_tx, from_address = check_buyer_and_seller_blockfrost_without_stake_address(
        utxo_list,
        buy_listing,
        sell_listing)

    if buyer_address != '':
        buyer_check = True
    if seller_address != '':
        seller_check = True

    for utxo in utxo_list:
        utxos.append(utxo)

    response = {
        'buyer_sent': buyer_check,
        'seller_sent': seller_check,
        'utxos': utxos
    }
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/connectwallet/status', methods=['POST'])
# Check whether the user has sent their verify lovelace to the address
async def connect_wallet_status_handler():
    data = await request.get_json()
    address = data['address']
    lovelace = str(data['verify_lovelace'])

    lovelace_found = False
    utxo_list = query_utxos(address)
    utxos = []
    for utxo in utxo_list:
        if utxo[2] == lovelace:
            lovelace_found = True
        utxos.append({'utxo': ' '.join(utxo)})

    response = {'lovelace_found': lovelace_found, 'utxos': utxos}

    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/connectwallet/finalize', methods=['POST'])
# Determine whether the user succeeds in adding a wallet and refund all utxos equal or larger than 2 ADA
async def connect_wallet_finalize_handler():
    if not os.path.isdir('request'):
        os.makedirs('request')
    data = await request.get_json()
    address = data['address']
    lovelace = str(data['verify_lovelace'])
    signing_key = data['signing_key']

    _id = get_unique_id()
    signing_key_path = f'request/payment_{_id}.skey'
    with open(signing_key_path, 'w') as file:
        json.dump(signing_key, file)

    stake_address, sender_utxo_address = get_user_addresses(address, lovelace)
    txid = return_all_utxos(address, signing_key_path)
    # print(txid)
    if stake_address is not None:
        response = {'status': 'success', 'stake_address': stake_address, 'txids': txid}
    else:
        response = {'status': 'failed', 'stake_address': stake_address, 'txids': txid}

    try:
        os.remove(signing_key_path)
    except FileNotFoundError as e:
        print(f'connect_wallet_finalize_handler: {e.errno}')
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/return/ada_only', methods=['POST'])
# Return all utxos which have only ADA and equal or more than 2 ADA
async def return_ada_only_handler():
    data = await request.get_json()
    address = data['address']
    signing_key = data['signing_key']
    if not os.path.isdir('request'):
        os.makedirs('request')
    _id = get_unique_id()
    signing_key_path = f'request/payment_{_id}.skey'
    with open(signing_key_path, 'w') as file:
        json.dump(signing_key, file)

    txid = refund_all_ada_utxos(address, signing_key_path)
    response = {'txids': txid}

    try:
        os.remove(signing_key_path)
    except FileNotFoundError as e:
        print(f'refund_ada_only_handler: {e.errno}')
        raise ValueError(f'refund_ada_only_handler: {e.errno}')

    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/return/all', methods=['POST'])
# Return all utxos regardless of coming from registered addresses or unregistered addresses
async def return_all_utxos_handler():
    data = await request.get_json()
    address = data['address']
    signing_key = data['signing_key']

    # Make directory
    if not os.path.isdir('request'):
        os.makedirs('request')

    # Write signing key to file
    _id = get_unique_id()
    signing_key_path = f'request/payment_{_id}.skey'
    with open(signing_key_path, 'w') as file:
        json.dump(signing_key, file)

    # Return utxos
    txid = return_all_utxos(address, signing_key_path)
    if len(txid) > 0:
        response = {'status': 'success'}
    else:
        response = {'status': 'failed'}
    response['txids'] = txid

    try:
        os.remove(signing_key_path)
    except FileNotFoundError as e:
        print(f'return_all_utxos_handler: {e.errno}')
        raise ValueError(f'return_all_utxos_handler: {e.errno}')

    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/return/registered', methods=['POST'])
# Return all utxos which send from registered addresses
async def return_all_registered_utxos_handler():
    data = await request.get_json()
    address = data['address']
    signing_key = data['signing_key']
    stake_list = []
    for stake_address in data['stake_list']:
        stake_list.append(stake_address['stake_address'])

    # Make directory
    if not os.path.isdir('request'):
        os.makedirs('request')

    # Write signing key to file
    _id = get_unique_id()
    signing_key_path = f'request/payment_{_id}.skey'
    with open(signing_key_path, 'w') as file:
        json.dump(signing_key, file)

    # Return utxos
    txid = return_all_registered_utxos(address, signing_key_path, stake_list)
    if len(txid) > 0:
        response = {'status': 'success'}
    else:
        response = {'status': 'failed'}
    response['txids'] = txid

    # Remove files
    try:
        os.remove(signing_key_path)
    except FileNotFoundError as e:
        print(f'return_all_registered_utxos_handler: {e.errno}')
        raise ValueError(f'return_all_registered_utxos_handler: {e.errno}')
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/support/reclaim/status', methods=['POST'])
async def reclaim_status_handler():
    # TODO need more testing
    data = await request.get_json()
    address = data['address']
    lovelace = str(data['verify_lovelace'])
    stake_list = []
    for stake_address in data['stake_list']:
        stake_list.append(stake_address['stake_address'])

    lovelace_found = False
    utxo_list = query_utxos(address)
    utxos = []
    for utxo in utxo_list:
        if utxo[2] == lovelace:
            tx = get_transaction_content(utxo[0])
            sender_utxo_address = tx['inputs'][0]['address']
            sender_stake_address = get_stake_address(sender_utxo_address)
            if sender_stake_address in stake_list:
                lovelace_found = True
        utxos.append({'utxo': ' '.join(utxo)})

    response = {'lovelace_found': lovelace_found, 'utxos': utxos}
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/support/reclaim/finalize', methods=['POST'])
async def reclaim_finalize_handler():
    # TODO need more testing
    data = await request.get_json()
    address = data['address']
    signing_key = data['signing_key']
    market_address = data['market_address']

    stake_list = []
    for stake_address in data['stake_list']:
        stake_list.append(stake_address['stake_address'])

    # Write signing key to file
    if not os.path.isdir('request'):
        os.makedirs('request')

    _id = get_unique_id()
    signing_key_path = f'request/payment_{_id}.skey'
    with open(signing_key_path, 'w') as file:
        json.dump(signing_key, file)

    # Make a directory to store transaction processing file
    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    # Query utxos in address
    utxo_list = query_utxos(address)

    check = False
    response = {'status': 'failed', 'txids': []}
    # mark utxo in utxo_list_bf: 0 is unregistered utxo, 1 is registered
    utxo_mark = [0] * len(utxo_list)
    from_address = [''] * len(utxo_list)
    cover_utxo_address = ''
    # Mark registered utxos, buyer and seller address
    for i, utxo in enumerate(utxo_list):
        tx = get_transaction_content(utxo[0])
        sender_utxo_address = tx['inputs'][0]['address']
        sender_stake_address = get_stake_address(sender_utxo_address)
        if sender_stake_address in stake_list:
            utxo_mark[i] = 1
            from_address[i] = sender_utxo_address
            if int(utxo[2]) >= 3000000:
                cover_utxo_address = from_address[i]
                check = True

    if check is False:
        return json.dumps(response), {'Content-Type': 'application/json'}

    # Calculate service fee
    service_fee = 1000000

    # Choose network
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    signed_path = ''
    _id = get_unique_id()
    draft_path = f'transactions/tx_{_id}.draft'

    # Build the transaction
    # tx-in
    build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build']
    for i, utxo in enumerate(utxo_list):
        if utxo_mark[i] == 1:
            build_parameters += ['--tx-in', f'{utxo[0]}#{utxo[1]}']

    # If tx-in is empty, return fail
    if len(build_parameters) <= 3:
        return json.dumps(response), {'Content-Type': 'application/json'}
    response['status'] = 'success'

    # tx-out
    build_parameters += ['--tx-out', f'{market_address}+{service_fee}']  # service fee
    for i, utxo in enumerate(utxo_list):
        if utxo_mark[i] == 1:
            if utxo[0] == cover_utxo_address:
                continue
            if len(utxo) <= 6:
                build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}']
            elif len(utxo) > 6:
                build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}'
                                                 f'+{utxo[5]} {utxo[6]}']
    if cover_utxo_address == '':
        raise ValueError(f'reclaim_finalize_handler: Not enough fund to cover network fee.'
                         f'Need at least 1 ADA-only utxo containing equal or more than 3 ADA.')
    build_parameters += ['--change-address', cover_utxo_address]

    # Set network
    build_parameters += net
    build_parameters += ['--out-file', draft_path, '--alonzo-era']

    # Build transaction

    output = run_command(build_parameters, my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output

    # Sign the transaction draft
    signed_path = f'transactions/tx_{_id}.signed'
    sign_parameters = [CARDANO_CLI_PATH, 'transaction', 'sign',
                       '--tx-body-file', draft_path,
                       '--signing-key-file', signing_key_path]
    sign_parameters += net
    sign_parameters += ['--out-file', signed_path]

    output = run_command(sign_parameters, my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output

    # Submit the transaction
    submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                         '--tx-file', signed_path]
    submit_parameters += net

    result = run_command(submit_parameters, my_env)
    if type(result) is subprocess.CalledProcessError:
        raise result

    # Record the txid
    txid_parameters = [CARDANO_CLI_PATH, 'transaction', 'txid', '--tx-file', signed_path]

    txid = run_command(txid_parameters, my_env)
    if type(txid) is subprocess.CalledProcessError:
        raise txid

    response['txids'] = [{'txid': txid.decode('utf-8').strip('\n')}]

    # Clean transaction files
    try:
        os.remove(signing_key_path)
        os.remove(signed_path)
        os.remove(draft_path)
    except FileNotFoundError as e:
        print(f'reclaim_finalize_handler: {e.errno}')

    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/transactions/outgoing/confirm', methods=['POST'])
# Description: check whether there's an outgoing transaction which sends to the addresses in the stake_list
async def confirm_outgoing_transaction_handler():
    data = await request.get_json()
    address = data['address']

    # Stake_list should include stake_address of buyer, seller, and market wallet ( wallet which receives fee)
    stake_list = []
    for stake_address in data['stake_list']:
        stake_list.append(stake_address['stake_address'])

    # status is failed as default
    response = {'status': 'failed'}

    # Sort transaction history with descending order by block_height
    transaction_list = get_transaction_history(address)
    transaction_list = sorted(transaction_list, key=(lambda x: int(x['block_height'])), reverse=True)

    # Find outgoing transaction which matches stake_list
    for transaction in transaction_list:
        tx = get_transaction_content(transaction['tx_hash'])
        if tx['inputs'][0]['address'] == address:
            check = True
            for receive in tx['outputs']:
                receive_address = receive['address']
                receive_stake_address = get_stake_address(receive_address)
                if receive_stake_address not in stake_list:
                    check = False
                    break
            if check is False:
                continue
            response['txid'] = tx['hash']
            response['block_height'] = transaction['block_height']
            response['status'] = 'success'
            break
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/transactions/<string:txid>/confirm', methods=['GET'])
# Description: check whether there's an outgoing transaction which sends to the addresses in the stake_list
async def confirm_transaction_handler(txid):
    print(txid)
    response = get_specific_transaction(txid)
    print(response)
    if 'error' in response:
        response = {'status': 'failed', 'message': 'Not found'}
    else:
        response = {'status': 'success'}
    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/server/status', methods=['GET'])
async def server_status_handler(network=NETWORK):
    # Query tip
    tip_parameters = [CARDANO_CLI_PATH, 'query', 'tip']
    if network == 'mainnet':
        tip_parameters += ['--mainnet']
    else:
        tip_parameters += ['--testnet-magic', TESTNET_MAGIC]

    check = False
    # Set status

    output = run_command(tip_parameters, my_env)
    if output is not subprocess.CalledProcessError:
        output = json.loads(output.decode('utf-8'))
        if float(output["syncProgress"]) == 100:
            check = True
    if check is True:
        return json.dumps({'status': 'online'}), 200, {'Content-Type': 'application/json'}
    else:
        return json.dumps({'status': 'offline'}), 503, {'Content-Type': 'application/json'}


@app.route('/v0/transactions/body', methods=['POST'])
async def transaction_body_handler():
    # Get data
    data = await request.get_json()
    sender_stake_address = data['sender_address']
    receiver_address = data['receiver_address']
    amount = data['amount']

    # Decode "unit" in amount to query format
    for a in amount:
        if len(a['unit']) > 56:
            asset_id = a['unit']
            # asset_name = bytes.fromhex(asset_id[56:]).decode("utf-8")
            a['unit'] = f'{asset_id[:56]}.{asset_id[56:]}'

    # Create package format to send
    package = [
        {
            'address': receiver_address,
            'amount': amount
        }
    ]

    response = get_transaction_body(sender_stake_address, package)
    if 'error' not in response:
        for out in response['output']:
            for a in out['amount']:
                if len(a['unit']) > 56:
                    asset = a['unit']
                    a['unit'] = asset[:56] + asset[57:]  # .encode('utf-8').hex() ,from 1.32.1 query is hex name

    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/transactions/id', methods=['POST'])
async def get_transaction_id_handler():
    # Get data
    data = await request.get_json()
    cbor_hex = data['cborHex']

    # Write signing key to file
    if not os.path.isdir('request'):
        os.makedirs('request')

    _id = get_unique_id()
    signed_path = f'request/tx_{_id}.signed'
    text = {
        "type": "Tx AlonzoEra",
        "description": "",
        "cborHex": cbor_hex
    }

    with open(signed_path, 'w') as file:
        json.dump(text, file)

    txid = get_txid(signed_path)
    response = {'txid': txid}

    # Clean transaction files
    try:
        os.remove(signed_path)
    except FileNotFoundError as e:
        print(f'submit_transaction_handler: {e.errno}')

    return json.dumps(response), {'Content-Type': 'application/json'}


@app.route('/v0/transactions/submit', methods=['POST'])
async def submit_transaction_handler():
    # Get data
    data = await request.get_json()
    cbor_hex = data['cborHex']

    # Write signing key to file
    if not os.path.isdir('request'):
        os.makedirs('request')

    _id = get_unique_id()
    signed_path = f'request/tx_{_id}.signed'
    text = {
        "type": "Tx AlonzoEra",
        "description": "",
        "cborHex": cbor_hex
    }

    with open(signed_path, 'w') as file:
        json.dump(text, file)

    txid = submit_transaction(signed_path)
    response = {"txid": txid}

    # Clean transaction files
    try:
        os.remove(signed_path)
    except FileNotFoundError as e:
        print(f'submit_transaction_handler: {e.errno}')

    return json.dumps(response), {'Content-Type': 'application/json'}


if __name__ == '__main__':
    # Prepare directories
    if not os.path.isdir('request'):
        os.makedirs('request')
    if not os.path.isdir('transactions'):
        os.makedirs('transactions')
    if not os.path.isdir('address'):
        os.makedirs('address')
    if not os.path.isdir('datum'):
        os.makedirs('datum')

    # Run the server
    load_logconfig()
    app.run(debug=True, host='0.0.0.0')
    # o = run_command(['ls','-l'], {} )
    # if type(o) is subprocess.CalledProcessError:
    #     print("Foo bar")

    # o = run_command(['ls','sdfasdf'], {} )
    # if type(o) is subprocess.CalledProcessError:
    #     print("Error Foo bar")
