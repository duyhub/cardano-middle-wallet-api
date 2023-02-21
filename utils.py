import requests
import subprocess
import json
import yaml
import logging
import time
from datetime import datetime
from uuid import uuid4

from enums import *
import inspect
import asyncio

"""
Subprocess Wrapper
"""

logger = logging.getLogger("default")


def load_logconfig():
    with open('logconfig.yml', 'rt') as f:
        config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)


def run_command(command, _env, timeout=None, stderr=subprocess.STDOUT):
    logger = logging.getLogger("default")
    func = inspect.currentframe().f_back.f_code
    logger.info("Caller: %s() - File: %s - LineNo: %s", func.co_name, func.co_filename, func.co_firstlineno)
    logger.info("Execute command: %s", command)
    try:
        output = subprocess.check_output(command, env=_env, timeout=timeout, stderr=stderr)
    except subprocess.CalledProcessError as exp:
        logger.error("Execution error: %s", exp.output)
        return exp
    logger.debug("Execution DONE!")
    return output


async def coroutine_run_command(command, _env, timeout=None, stderr=subprocess.STDOUT):
    # TODO
    logger = logging.getLogger("default")
    func = inspect.currentframe().f_back.f_code
    logger.info("Caller: %s() - File: %s - LineNo: %s", func.co_name, func.co_filename, func.co_firstlineno)
    logger.info("Execute command: %s", command)
    try:
        output = await asyncio.create_subprocess_shell(command, env=_env, timeout=timeout, stderr=stderr)
    except subprocess.CalledProcessError as exp:
        logger.error("Execution error: %s", exp.output)
        return exp
    logger.debug("Execution DONE!")
    return output


"""
Blockchain utility methods
"""


def get_unique_id():
    event_id = datetime.now().strftime('%Y%m-%d%H-%M%S-') + str(uuid4())
    return event_id


def query_utxos(address):
    # Description: Return available utxos information in the address
    start = time.time()
    raw_utxo_table = None
    # cardano-cli query utxo
    if NETWORK == 'mainnet':
        raw_utxo_table = run_command([CARDANO_CLI_PATH, 'query', 'utxo',
                                      '--mainnet',
                                      '--address', address], _env=my_env)
    elif NETWORK == 'testnet':
        raw_utxo_table = run_command([
            CARDANO_CLI_PATH, 'query', 'utxo',
            '--testnet-magic', TESTNET_MAGIC,
            '--address', address], _env=my_env)
    if type(raw_utxo_table) is subprocess.CalledProcessError:
        pass
        raise raw_utxo_table

    # Get utxos
    if type(raw_utxo_table) is subprocess.CalledProcessError:
        raise raw_utxo_table

    utxo_list = []
    utxo_table_rows = raw_utxo_table.strip().splitlines()
    for x in range(2, len(utxo_table_rows)):
        cells = utxo_table_rows[x].split()
        for i in range(len(cells)):
            cells[i] = cells[i].decode('utf-8').strip('"')
        utxo_list.append(cells)

    print(f'query_utxos {address}: {time.time() - start} seconds')
    return utxo_list


async def coroutine_query_utxos(address):
    # TODO
    # Description: Return available utxos information in the address
    start = time.time()
    raw_utxo_table = None
    # cardano-cli query utxo
    if NETWORK == 'mainnet':
        raw_utxo_table = run_command([CARDANO_CLI_PATH, 'query', 'utxo',
                                      '--mainnet',
                                      '--address', address], _env=my_env)
    elif NETWORK == 'testnet':
        raw_utxo_table = run_command([
            CARDANO_CLI_PATH, 'query', 'utxo',
            '--testnet-magic', TESTNET_MAGIC,
            '--address', address], _env=my_env)
    if type(raw_utxo_table) is subprocess.CalledProcessError:
        pass
        raise raw_utxo_table

    # Get utxos
    if type(raw_utxo_table) is subprocess.CalledProcessError:
        raise raw_utxo_table

    utxo_list = []
    utxo_table_rows = raw_utxo_table.strip().splitlines()
    for x in range(2, len(utxo_table_rows)):
        cells = utxo_table_rows[x].split()
        for i in range(len(cells)):
            cells[i] = cells[i].decode('utf-8').strip('"')
        utxo_list.append(cells)

    print(f'query_utxos {address}: {time.time() - start} seconds')
    return utxo_list


def query_utxos_by_stake_address(stake_address):
    response_list = get_address_list_by_stake_address(stake_address)
    print(f'response_list: {response_list}')
    sender_address_list = []
    for address in response_list:
        sender_address_list.append(address['address'])

    utxo_list = []
    for address in sender_address_list:
        utxo_list += query_utxos(address)
    return utxo_list


def query_utxos_blockfrost(_address):
    api_key = BLOCKFROST_API_KEY
    headers = {'project_id': api_key}
    utxo_list = []
    cnt = 1
    while True:
        url = f'https://cardano-{NETWORK}.blockfrost.io/api/v0/addresses/{_address}/utxos?page={cnt}'
        response = requests.request('GET', url=url, headers=headers)
        utxo_list += response.json()
        print(response.json())
        if 'error' in response.json():
            raise ValueError('query_utxos_blockfrost: Bad Request')
        if len(response.json()) == 0:
            break
        cnt += 1
    print(f'query_utxos_blockfrost: {utxo_list}')
    return utxo_list


def get_protocol_file_path():
    # Description: Make a protocol.json file
    # Return: file path of protocol file

    if not os.path.isdir('protocol'):
        os.makedirs('protocol')

    # Choose network
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    protocol_path = f'protocol/protocol.json'
    protocol_parameters = [CARDANO_CLI_PATH, 'query', 'protocol-parameters']
    protocol_parameters += net
    protocol_parameters += ['--out-file', protocol_path]

    output = run_command(protocol_parameters, _env=my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output
    return protocol_path


def calculate_min_required_utxo(tx_out, datum_hash=None):
    """
    Calculate the minimum required UTxO for a transaction
    :param tx_out:
    :param datum_hash:
    :return:
    """
    # print(f'calculate_txout: {tx_out}')
    build_parameters = [CARDANO_CLI_PATH, 'transaction', 'calculate-min-required-utxo']
    build_parameters += ['--alonzo-era', '--protocol-params-file', 'protocol/protocol.json']
    build_parameters += ['--tx-out', tx_out]
    if datum_hash is not None:
        build_parameters += ['--tx-out-datum-hash', datum_hash]

    output = run_command(build_parameters, _env=my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output

    output = output.decode('utf-8').split()
    return int(output[1])


def calculate_min_value(multi_asset_string):
    # Description: calculate minimum ADA value for multi-asset utxo
    # Parameters: ()
    #           multi_asset_string: a string format when sending out as utxo
    # For example: multi_asset_string = "2 6b8d07d69639e9413dd637a1a815a7323c69c86abbafb66dbfdb1aa7"
    #               2 is quantity, 6b8d.. is {policyid}.{assetname} or {policyid}
    # Return: the amount of minimum ADA requirement in string

    min_value_parameters = [CARDANO_CLI_PATH, 'transaction', 'calculate-min-value']
    min_value_parameters += ['--protocol-params-file', get_protocol_file_path()]
    min_value_parameters += ['--multi-asset', multi_asset_string]

    min_value = run_command(min_value_parameters, _env=my_env)
    if type(min_value) is subprocess.CalledProcessError:
        raise min_value

    min_value.strip().splitlines()
    min_value = min_value.decode('utf-8').split()
    print(min_value)
    return min_value[1]


def create_wallet_address(network=NETWORK):
    # Tools: cardano-cli
    # Description: Create a new payment address, verification_key, signing_key and locate them in
    #   payment.addr, payment.vkey, payment.skey
    # Parameters:
    #           network == mainnet or testnet

    # Check if address folder exists
    if not os.path.isdir('address'):
        os.makedirs('address')
    # Create non duplicated file each time this method called
    while True:
        _id = get_unique_id()
        file_path = f'address/payment_{_id}.addr'
        try:
            with open(file_path) as _file:
                _file.close()
            _id += 1
        except FileNotFoundError:
            break

    # Create payment key pair
    payment_verification_key_path = f"address/payment_{_id}.vkey"
    payment_signing_key_path = f"address/payment_{_id}.skey"
    output = run_command([
        CARDANO_CLI_PATH, 'address', 'key-gen',
        '--verification-key-file', payment_verification_key_path,
        '--signing-key-file', payment_signing_key_path
    ])

    if type(output) is subprocess.CalledProcessError:
        raise output

    # Create stake key pair
    stake_verification_key_path = f'address/stake_{_id}.vkey'
    stake_signing_key_path = f'address/stake_{_id}.skey'
    output = run_command([
        CARDANO_CLI_PATH, 'stake-address', 'key-gen',
        '--verification-key-file', stake_verification_key_path,
        '--signing-key-file', stake_signing_key_path
    ])
    if type(output) is subprocess.CalledProcessError:
        raise output

    # Create payment address
    payment_address_path = f'address/payment_{_id}.addr'
    if network == 'testnet':
        output = run_command([
            CARDANO_CLI_PATH, 'address', 'build',
            '--payment-verification-key-file', payment_verification_key_path,
            '--stake-verification-key-file', stake_verification_key_path,
            '--out-file', payment_address_path,
            '--testnet-magic', TESTNET_MAGIC
        ])
        if type(output) is subprocess.CalledProcessError:
            raise output

    elif network == 'mainnet':
        output = run_command([
            CARDANO_CLI_PATH, 'address', 'build',
            '--payment-verification-key-file', payment_verification_key_path,
            '--stake-verification-key-file', stake_verification_key_path,
            '--out-file', payment_address_path,
            '--mainnet'
        ])
        if type(output) is subprocess.CalledProcessError:
            raise output

    # Create stake address
    # stake_address_path = f'address/stake_{_id}.addr'
    # if network == 'testnet':
    #     output = run_command([
    #         CARDANO_CLI_PATH, 'stake-address', 'build',
    #         '--stake-verification-key-file', stake_verification_key_path,
    #         '--out-file', stake_address_path,
    #         '--testnet-magic', TESTNET_MAGIC
    #     ])
    # if type(output) is subprocess.CalledProcessError:
    #     raise output
    # elif network == 'mainnet':
    #     output = run_command([
    #         CARDANO_CLI_PATH, 'stake-address', 'build',
    #         '--stake-verification-key-file', stake_verification_key_path,
    #         '--out-file', stake_address_path,
    #         '--mainnet'
    #     ])
    # if type(output) is subprocess.CalledProcessError:
    #     raise output

    with open(payment_address_path, 'r') as file:
        payment_address = file.read()
    with open(payment_verification_key_path, 'r') as file:
        payment_verification_key = json.loads(file.read())
    with open(payment_signing_key_path, 'r') as file:
        payment_signing_key = json.loads(file.read())
    output = {
        'address': payment_address,
        'verification_key': payment_verification_key,
        'signing_key': payment_signing_key
    }
    try:
        os.remove(payment_address_path)
        os.remove(payment_verification_key_path)
        os.remove(payment_signing_key_path)
        os.remove(stake_signing_key_path)
        os.remove(stake_verification_key_path)
        # print(payment_address_path)
    except FileNotFoundError as e:
        print(f'create_wallet_address: {e.errno}')
        raise ValueError(f'create_wallet_address: {e.errno}')
    return json.dumps(output)


def get_stake_address(_address):
    # Note: a brand-new payment address without any utxo won't have a stake_address
    # --------------------------------------------------------------------------------
    # Tools: blockfrost.io
    # Description: Find a stake address associated with _address
    # Parameters:
    #           _address: requested address
    # Return: stake address

    api_key = BLOCKFROST_API_KEY
    headers = {'project_id': api_key}
    url = f'https://cardano-{NETWORK}.blockfrost.io/api/v0/addresses/{_address}'
    response = requests.request('GET', url=url, headers=headers)
    # print(url)
    # print(response.json())
    if 'error' in response.json():
        print('Stake address\'s not found')
        return 'error'
    return response.json()['stake_address']


def get_transaction_content(tx_hash):
    # Tools: blockfrost.io
    # Description: Extract info from tx_hash
    # Parameters:
    #           tx_hash: Hash of the requested transaction
    # Return: Return the contents of a transaction

    api_key = BLOCKFROST_API_KEY
    headers = {'project_id': api_key}
    url = f'https://cardano-{NETWORK}.blockfrost.io/api/v0/txs/{tx_hash}/utxos'
    response = requests.request('GET', url=url, headers=headers)
    return response.json()


def get_transaction_history(_address):
    # Tools: blockfrost.io
    # Description: Find transaction history of an address
    # Parameters:
    #           _address: requested address
    # Return: address' transaction ids

    # Get all utxos existed in this address throughout history (first 100 pages)
    utxo_list = []
    for i in range(100):
        i += 1
        # Get utxos in each page, max 100
        url = f'https://cardano-{NETWORK}.blockfrost.io/api/v0/addresses/{_address}/transactions?page={i}'
        api_key = BLOCKFROST_API_KEY
        headers = {'project_id': api_key}
        response = requests.request('GET', url=url, headers=headers)
        # print(len(response.json()))
        if len(response.json()) == 0:
            break
        # print(response.json())
        if response.status_code != 200:
            raise ValueError(f'get_transaction_history: the address does not exist or cannot be found.'
                             f'\n{response.text}')
        utxo_list = utxo_list + response.json()

    # Expand utxo_list_bf into details:
    # contents = []
    # for tx in utxo_list_bf:
    #     contents.append(get_transaction_content(tx['tx_hash']))
    # print(contents)
    return utxo_list


def list_assets_by_stake_address(_stake_address):
    # Tools: blockfrost.io
    # Description: Find list of assets associated with the stake address
    # Parameters:
    #            _stake_address: a stake address
    # Return: list of dictionary with format: {asset_id, quantity} with type {str,int}
    #         asset_id is the concatenation of the policy_id (56 characters) and hex-encoded asset_name
    #
    # Output example:
    # [{'6b8d07d69639e9413dd637a1a815a7323c69c86abbafb66dbfdb1aa7': 3},
    #  {'b0d07d45fe9514f80213f4020e5a61241458be626841cde717cb38a76e7574636f696e': 5}]

    i = 0
    asset_list = []
    while True:
        i += 1
        url = f'https://cardano-{NETWORK}.blockfrost.io/api/v0/accounts/{_stake_address}/addresses/assets?page={i}'
        api_key = BLOCKFROST_API_KEY
        headers = {'project_id': api_key}
        response = requests.request('GET', url=url, headers=headers)
        if len(response.json()) == 0:
            break
        asset_list = asset_list + response.json()

    # Test multiple assets by adding 'abcxyz'
    # asset_list.append({'unit': 'b0d07d45fe9514f80213f4020e5a61241458be626841cde717cb38a76e7574636f696e',
    #                    'quantity': '5'})

    temp_dict = {}
    # temp_dict: Temporary variables to merge duplicate assets
    #           key - asset_id
    #           value - quantity of that asset
    for asset in asset_list:
        asset_id = asset['unit']
        quantity = int(asset['quantity'])
        if asset_id in temp_dict:
            temp_dict[asset_id] += quantity
        else:
            temp_dict[asset_id] = quantity

    assets = []
    for key in temp_dict:
        assets.append({key: temp_dict[key]})

    return assets


def get_asset(_asset):
    # Tools: blockfrost.io
    # Description: Get detail of a specific asset
    # Parameters:
    #           _asset: asset id of an asset
    # Return: asset information - asset_policy id, asset name, metadata,...

    api_key = BLOCKFROST_API_KEY
    headers = {'project_id': api_key}
    url = f'https://cardano-{NETWORK}.blockfrost.io/api/v0/assets/{_asset}'
    response = requests.request('GET', url=url, headers=headers)
    return response.json()


def get_assets_of_specific_policy(policy_id):
    """
    Get assets' asset_policy list of a specific asset_policy
    :param policy_id: asset_policy id of that asset_policy
    :return: list of assets' asset_policy
    """
    cnt = 1
    asset_list = []
    sum = 0
    while True:
        url = f'https://cardano-{NETWORK}.blockfrost.io/api/v0/assets/policy/{policy_id}?page={cnt}'
        api_key = BLOCKFROST_API_KEY
        headers = {'project_id': api_key}
        response = requests.request('GET', url=url, headers=headers)
        sum += len(response.json())
        if len(response.json()) == 0:
            break
        asset_list += response.json()
        cnt += 1
    print(f'cnt = {cnt}')
    print(f'sum = {sum}')
    return asset_list


def address_of_asset(asset_policy):
    """
    Get address holder(s) of a specific asset
    :param asset_policy: policy of an asset
    :return: list of addresses containing that asset
    """

    # TODO: add multi-page of addresses
    url = f'https://cardano-{NETWORK}.blockfrost.io/api/v0/assets/{asset_policy}/addresses'
    api_key = BLOCKFROST_API_KEY
    headers = {'project_id': api_key}
    response = requests.request('GET', url=url, headers=headers)
    return response.json()


def address_list_of_specific_policy(policy_id):
    """
    Get address list of a specific asset_policy
    :param policy_id: asset_policy id of the asset_policy
    :return: list of addresses containing assets of the asset_policy
    """
    asset_list = get_assets_of_specific_policy(policy_id)
    address_list = set()
    for asset in asset_list:
        asset_policy = asset['asset']
        addresses = address_of_asset(asset_policy)
        for address in addresses:
            # print(address['address'])
            address_list.add(address['address'])
            # print(address_list)
    return address_list


def get_user_addresses(payment_address, verify_amount):
    # Description: Find the stake_address of the sender's address which sends
    #               the verify_amount to the payment_address located in sender_address_path
    # Parameters: (string, int)
    #           payment_address: the verifying address created by server
    #           verify_amount: the exact amount of LOVELACE received from the user to verify his/her wallet
    # Return:
    #           stake_address of the sender who sends <verify_amount> lovelace
    #           sender_utxo_address: to send the verifying lovelace back

    sender_utxo_address = None
    stake_address = None
    transaction_history = []

    # Query UTXO and read the output
    raw_utxo_table = None
    if NETWORK == 'mainnet':
        raw_utxo_table = run_command([
            CARDANO_CLI_PATH, 'query', 'utxo',
            '--mainnet',
            '--address', payment_address], _env=my_env)
    elif NETWORK == 'testnet':
        raw_utxo_table = run_command([
            CARDANO_CLI_PATH, 'query', 'utxo',
            '--testnet-magic', TESTNET_MAGIC,
            '--address', payment_address], _env=my_env)
    # print(raw_utxo_table[2])
    if type(raw_utxo_table) is subprocess.CalledProcessError:
        raise raw_utxo_table

    found = False
    # Calculate total lovelace of the UTXO(s) inside the wallet address
    utxo_table_rows = raw_utxo_table.strip().splitlines()
    for x in range(2, len(utxo_table_rows)):
        cells = utxo_table_rows[x].split()

        # If utxo includes a token -> skip
        if len(cells) > 6:
            continue
        if cells[2].decode('utf-8') == str(verify_amount):
            transaction_history.append(get_transaction_content(cells[0].decode('utf-8')))
            found = True
            break
    # print(transaction_history)
    if found is True:
        for tx in transaction_history:
            for utxo in tx['outputs']:
                if utxo['address'] == payment_address:
                    for unit in utxo['amount']:
                        if unit['unit'] == 'lovelace' \
                                and unit['quantity'] == str(verify_amount):
                            sender_utxo_address = tx['inputs'][0]['address']

    # print(found)

    if found is True:
        stake_address = get_stake_address(sender_utxo_address)

    return stake_address, sender_utxo_address


def get_address_list_by_stake_address(stake_address):
    """
    Get list of addresses associated with stake address
    :param stake_address: stake address
    :return: list of addresses
    """
    cnt = 0
    response_list = []
    while True:
        cnt += 1
        url = f'https://cardano-{NETWORK}.blockfrost.io/api/v0/accounts/{stake_address}/addresses?page={cnt}'
        api_key = BLOCKFROST_API_KEY
        # print(api_key)
        # print(url)
        headers = {'project_id': api_key}
        response = requests.request('GET', url=url, headers=headers)
        if 'error' in response.json():
            raise ValueError(f'Error in get_address_list_by_stake_address: {response.json()["error"]}')
        response_list += response.json()
        # print(response.json())
        if len(response.json()) == 0:
            break
    print(len(response_list))
    return response_list


def get_balance_by_stake_address(stake_address):
    """
    Get total ADA and list of assets associated with stake_address
    :param stake_address: stake address
    :return: list of assets, their quantities and total amount of lovelace
    """

    # Get list of addresses
    response_list = get_address_list_by_stake_address(stake_address)
    address_list = []
    for address in response_list:
        address_list.append(address['address'])

    # print(address_list)
    account = {}
    for address in address_list:
        utxo_list = query_utxos(address)
        # print(utxo_list_bf)
        for utxo in utxo_list:
            pairs = [(i + 2, i + 3) for i in range(0, len(utxo) - 3, 3)]
            # print(len(utxo))
            # print(pairs)
            for pair in pairs:
                unit_pos = pair[1]
                quantity_pos = pair[0]
                unit = utxo[unit_pos]
                quantity = utxo[quantity_pos]
                if unit in account:
                    account[unit] += int(quantity)
                else:
                    account[unit] = int(quantity)

    # Change to json response format
    response = []
    for key, value in account.items():
        if key != 'lovelace':
            asset_name = ''
            components = key.split(".")
            policy_id = components[0]
            if len(components) > 1:
                asset_name = components[1]
            temp = asset_name.encode('utf-8').hex()
            policy = policy_id + temp
        else:
            policy = key
        response.append({'unit': policy, 'quantity': str(value)})

    print(len(response))
    return response


def check_buyer_and_seller(utxo_list, buyer_stake_list, seller_stake_list, buy_listing, sell_listing):
    """
    Check if buyer has sent ADA and seller has sent asset(s)
    :param utxo_list:
    :param buyer_stake_list:
    :param seller_stake_list:
    :param buy_listing:
    :param sell_listing:
    :return: buyer_address, ada_tx, seller_address, asset_tx, utxo_mark, from_address
    """

    buy_quantity = str(buy_listing['quantity'])
    sell_quantity = str(sell_listing['quantity'])

    # Decode "unit" in buy_listing and sell_listing to query format
    if len(buy_listing['unit']) > 56:
        asset_id = buy_listing['unit']
        # asset_name = bytes.fromhex(asset_id[56:]).decode("utf-8")
        buy_listing['unit'] = f'{asset_id[:56]}.{asset_id[56:]}'

    if len(sell_listing['unit']) > 56:
        asset_id = sell_listing['unit']
        # asset_name = bytes.fromhex(asset_id[56:]).decode("utf-8")
        sell_listing['unit'] = f'{asset_id[:56]}.{asset_id[56:]}'

    # Declare variables
    buyer_address = ''
    seller_address = ''
    ada_tx = ''
    asset_tx = ''

    # mark utxo in utxo_list_bf: 0 is unregistered utxo, 1 is registered
    utxo_mark = [0] * len(utxo_list)
    from_address = [''] * len(utxo_list)

    # Mark registered utxos, buyer and seller address
    for i, utxo in enumerate(utxo_list):
        tx = get_transaction_content(utxo[0])
        sender_utxo_address = tx['inputs'][0]['address']
        sender_stake_address = get_stake_address(sender_utxo_address)
        if sender_stake_address in buyer_stake_list:
            utxo_mark[i] = 1
            from_address[i] = sender_utxo_address
            if len(utxo) <= 6 and utxo[3] == buy_listing['unit'] and utxo[2] == buy_quantity:
                buyer_address = sender_utxo_address
                ada_tx = utxo[0]
        if sender_stake_address in seller_stake_list:
            utxo_mark[i] = 1
            from_address[i] = sender_utxo_address
            if len(utxo) == 9 and utxo[6] == sell_listing['unit'] and utxo[5] == sell_quantity:
                seller_address = sender_utxo_address
                asset_tx = utxo[0]

    return buyer_address, ada_tx, seller_address, asset_tx, utxo_mark, from_address


def check_buyer_and_seller_without_stake_address(utxo_list, buy_listing, sell_listing):
    """
    Check if buyer has sent ADA and seller has sent asset(s), no restriction by stake address
    :param utxo_list:
    :param buyer_stake_list:
    :param seller_stake_list:
    :param buy_listing:
    :param sell_listing:
    :return: buyer_address, ada_tx, seller_address, asset_tx, utxo_mark, from_address
    """

    buy_quantity = str(buy_listing['quantity'])
    sell_quantity = str(sell_listing['quantity'])

    # Decode "unit" in buy_listing and sell_listing to query format
    if len(buy_listing['unit']) > 56:
        asset_id = buy_listing['unit']
        # asset_name = bytes.fromhex(asset_id[56:]).decode("utf-8")
        buy_listing['unit'] = f'{asset_id[:56]}.{asset_id[56:]}'

    if len(sell_listing['unit']) > 56:
        asset_id = sell_listing['unit']
        # asset_name = bytes.fromhex(asset_id[56:]).decode("utf-8")
        sell_listing['unit'] = f'{asset_id[:56]}.{asset_id[56:]}'

    # Declare variables
    buyer_address = ''
    seller_address = ''
    ada_tx = ''
    asset_tx = ''

    # mark utxo in utxo_list_bf: 0 is unregistered utxo, 1 is registered
    # utxo_mark = [0] * len(utxo_list)
    from_address = [''] * len(utxo_list)

    # Mark registered utxos, buyer and seller address
    for i, utxo in enumerate(utxo_list):
        tx = get_transaction_content(utxo[0])
        sender_utxo_address = tx['inputs'][0]['address']
        # sender_stake_address = get_stake_address(sender_utxo_address)
        # if sender_stake_address in buyer_stake_list:
        #     utxo_mark[i] = 1
        from_address[i] = sender_utxo_address
        if len(utxo) <= 6 and utxo[3] == buy_listing['unit'] and utxo[2] == buy_quantity:
            buyer_address = sender_utxo_address
            ada_tx = utxo[0]
        # if sender_stake_address in seller_stake_list:
        #     utxo_mark[i] = 1
        # from_address[i] = sender_utxo_address
        if len(utxo) == 9 and utxo[6] == sell_listing['unit'] and utxo[5] == sell_quantity:
            seller_address = sender_utxo_address
            asset_tx = utxo[0]

    return buyer_address, ada_tx, seller_address, asset_tx, from_address


def check_buyer_and_seller_blockfrost(utxo_list_bf, buyer_stake_list, seller_stake_list, buy_listing, sell_listing):
    """
    Check if buyer has sent ADA and seller has sent asset(s)
    :param utxo_list_bf:
    :param buyer_stake_list:
    :param seller_stake_list:
    :param buy_listing:
    :param sell_listing:
    :return: buyer_address, ada_tx, seller_address, asset_tx, utxo_mark, from_address
    """

    buy_quantity = str(buy_listing['quantity'])
    sell_quantity = str(sell_listing['quantity'])

    # Decode "unit" in buy_listing and sell_listing to query format
    # if len(buy_listing['unit']) > 56:
    #     asset_id = buy_listing['unit']
    #     # asset_name = bytes.fromhex(asset_id[56:]).decode("utf-8")
    #     buy_listing['unit'] = f'{asset_id[:56]}.{asset_id[56:]}'
    #
    # if len(sell_listing['unit']) > 56:
    #     asset_id = sell_listing['unit']
    #     # asset_name = bytes.fromhex(asset_id[56:]).decode("utf-8")
    #     sell_listing['unit'] = f'{asset_id[:56]}.{asset_id[56:]}'

    # Declare variables
    buyer_address = ''
    seller_address = ''
    ada_tx = ''
    asset_tx = ''

    # mark utxo in utxo_list_bf: 0 is unregistered utxo, 1 is registered
    utxo_mark = [0] * len(utxo_list_bf)
    from_address = [''] * len(utxo_list_bf)

    # Mark registered utxos, buyer and seller address
    for i, utxo in enumerate(utxo_list_bf):
        tx = get_transaction_content(utxo['tx_hash'])
        sender_utxo_address = tx['inputs'][0]['address']
        sender_stake_address = get_stake_address(sender_utxo_address)
        if sender_stake_address in buyer_stake_list:
            utxo_mark[i] = 1
            from_address[i] = sender_utxo_address
            if len(utxo['amount']) == 1:
                unit = utxo['amount'][0]['unit']
                quantity = utxo['amount'][0]['quantity']
                if unit == buy_listing['unit'] and quantity == buy_quantity:
                    buyer_address = sender_utxo_address
                    ada_tx = utxo['tx_hash']
        if sender_stake_address in seller_stake_list:
            utxo_mark[i] = 1
            from_address[i] = sender_utxo_address
            unit = ''
            quantity = ''
            if len(utxo['amount']) == 2:
                for a in utxo['amount']:
                    if a['unit'] != 'lovelace':
                        unit = a['unit']
                        quantity = a['quantity']
                        break
                if unit == sell_listing['unit'] and quantity == sell_quantity:
                    seller_address = sender_utxo_address
                    asset_tx = utxo['tx_hash']

    return buyer_address, ada_tx, seller_address, asset_tx, utxo_mark, from_address


def check_buyer_and_seller_blockfrost_without_stake_address(utxo_list_bf, buy_listing, sell_listing):
    """
    Check if buyer has sent ADA and seller has sent asset(s)
    :param utxo_list_bf:
    :param buyer_stake_list:
    :param seller_stake_list:
    :param buy_listing:
    :param sell_listing:
    :return: buyer_address, ada_tx, seller_address, asset_tx, utxo_mark, from_address
    """

    buy_quantity = str(buy_listing['quantity'])
    sell_quantity = str(sell_listing['quantity'])

    # Declare variables
    buyer_address = ''
    seller_address = ''
    ada_tx = ''
    asset_tx = ''

    # mark utxo in utxo_list_bf: 0 is unregistered utxo, 1 is registered
    # utxo_mark = [0] * len(utxo_list_bf)
    from_address = [''] * len(utxo_list_bf)

    # Mark registered utxos, buyer and seller address
    for i, utxo in enumerate(utxo_list_bf):
        tx = get_transaction_content(utxo['tx_hash'])
        sender_utxo_address = tx['inputs'][0]['address']
        # sender_stake_address = get_stake_address(sender_utxo_address)
        # if sender_stake_address in buyer_stake_list:
        #     utxo_mark[i] = 1
        from_address[i] = sender_utxo_address
        if len(utxo['amount']) == 1:
            unit = utxo['amount'][0]['unit']
            quantity = utxo['amount'][0]['quantity']
            if unit == buy_listing['unit'] and quantity == buy_quantity:
                buyer_address = sender_utxo_address
                ada_tx = utxo['tx_hash']
        # if sender_stake_address in seller_stake_list:
        #     utxo_mark[i] = 1
        #     from_address[i] = sender_utxo_address
        unit = ''
        quantity = ''
        if len(utxo['amount']) == 2:
            for a in utxo['amount']:
                if a['unit'] != 'lovelace':
                    unit = a['unit']
                    quantity = a['quantity']
                    break
            if unit == sell_listing['unit'] and quantity == sell_quantity:
                seller_address = sender_utxo_address
                asset_tx = utxo['tx_hash']

    return buyer_address, ada_tx, seller_address, asset_tx, from_address


def add_utxo_to_dict(_dict, utxo):
    pairs = [(i + 2, i + 3) for i in range(0, len(utxo) - 3, 3)]
    for pair in pairs:
        unit_pos = pair[1]
        quantity_pos = pair[0]
        unit = utxo[unit_pos]
        quantity = utxo[quantity_pos]
        if quantity == 'TxOutDatumHash':
            break
        if unit in _dict:
            _dict[unit] += int(quantity)
        else:
            _dict[unit] = int(quantity)
    return _dict


def to_tx_out(recipient_address, utxo):
    _list = {}
    _list = add_utxo_to_dict(_list, utxo)

    # Calculate minimum lovelace required for utxo
    txout_records = [f'{_list[key]} {key}' for key in _list if _list[key] > 0]
    tx_out = f"{recipient_address}+{'+'.join(txout_records)}"
    min_lovelace = calculate_min_required_utxo(tx_out)
    _list['lovelace'] = int(min_lovelace)

    # Add minimum lovelace
    txout_records = [f'{_list[key]} {key}' for key in _list if _list[key] > 0]
    tx_out = f"{recipient_address}+{'+'.join(txout_records)}"
    return tx_out


def calculate_fee(txin_list, txout_list, protocol_path):
    # Choose network
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    # Make directory
    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    # Build transaction
    # tx-in
    build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build-raw']
    for txin in txin_list:
        build_parameters += ['--tx-in', txin]

    # tx-out
    for txout in txout_list:
        build_parameters += ['--tx-out', txout]

    _id = get_unique_id()
    build_parameters += ['--fee', '0']
    draft_path = f'transactions/tx_{_id}.draft'
    build_parameters += ['--out-file', draft_path, '--alonzo-era']

    output = run_command(build_parameters, _env=my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output

    # Calculate-min-fee
    build_parameters = [CARDANO_CLI_PATH, 'transaction', 'calculate-min-fee']
    build_parameters += ['--tx-body-file', draft_path]
    build_parameters += ['--tx-in-count', str(len(txin_list))]
    build_parameters += ['--tx-out-count', str(len(txout_list))]
    build_parameters += ['--witness-count', '1']
    build_parameters += net
    build_parameters += ['--protocol-params-file', protocol_path]

    output = run_command(build_parameters, _env=my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output
    # Clean draft file
    try:
        os.remove(draft_path)
    except FileNotFoundError as e:
        print(f'calculate_min_fee: {e.errno}')

    fee = output.split()[0]
    fee = fee.decode('utf-8').strip('\n')
    return int(fee)


def check_enough_fund(sender_balance, package_balance):
    """
    Check if sender wallet has enough ADAs and assets to send out as the requested package
    :param sender_balance: dict
    :param package_balance: dict
    :return: True or False
    """
    # print('check enough fund')
    # print(sender_balance)
    # print(package_balance)
    for key in package_balance:
        if key not in sender_balance:
            return False
        elif package_balance[key] > sender_balance[key]:
            return False
        lovelace_difference = int(sender_balance['lovelace']) - int(package_balance['lovelace'])
        if 0 < lovelace_difference < 1000000:
            return False
    return True


def address_key_hash(verification_key):
    """
    Get hash of an address key
    :param verification_key:
    :return: key_hash
    """
    _id = get_unique_id()
    verification_key_file_path = f'address/verification_key_{_id}'
    with open(verification_key_file_path, 'w') as file:
        json.dump(verification_key, file)
    parameter = [CARDANO_CLI_PATH, 'address', 'key-hash', '--payment-verification-key-file', verification_key_file_path]

    key_hash = run_command(parameter, _env=my_env)
    if type(key_hash) is subprocess.CalledProcessError:
        raise key_hash
    key_hash = key_hash.decode('utf-8').strip('\n')

    # Clean verification key files
    try:
        os.remove(verification_key_file_path)
    except FileNotFoundError:
        print(f'address_key_hash: Error in remove files')

    return key_hash


def hash_script_data(datum_json_file_path):
    """
    Calculate the hash of script data
    :param datum_json_file_path:
    :return: datum_hash
    """
    parameter = [CARDANO_CLI_PATH, 'transaction', 'hash-script-data', '--script-data-file', datum_json_file_path]

    datum_hash = run_command(parameter, _env=my_env)
    if type(datum_hash) is subprocess.CalledProcessError:
        raise datum_hash
    datum_hash = datum_hash.decode('utf-8').strip('\n')
    return datum_hash


def hash_script_data_from_json(datum_json):
    """
    Calculate the hash of script data
    :param datum_json:
    :return: datum_hash
    """
    parameter = [CARDANO_CLI_PATH, 'transaction', 'hash-script-data', '--script-data-value', datum_json]
    datum_hash = run_command(parameter, _env=my_env)
    if type(datum_hash) is subprocess.CalledProcessError:
        raise datum_hash
    datum_hash = datum_hash.decode('utf-8').strip('\n')
    return datum_hash


def get_script_address(script_file_path):
    """
    Get a script address from .plutus file
    :param script_file_path:
    :return: script_address
    """
    # Choose network
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    parameters = [CARDANO_CLI_PATH, 'address', 'build', '--payment-script-file', script_file_path]
    parameters += net
    output = run_command(parameters, _env=my_env)
    if type(output) is subprocess.CalledProcessError:
        raise output
    script_address = output.decode('utf-8').strip('\n')
    return script_address


def combine_dict_package(package_1, package_2):
    """
    Combine 2 packages to one package
    :param package_1:
    :param package_2:
    :return:
    """
    a = package_1.copy()
    b = package_2.copy()
    for key in package_1:
        if key in b:
            b[key] += int(a[key])
        else:
            b[key] = int(a[key])
    return b


def get_specific_transaction(txid):
    api_key = BLOCKFROST_API_KEY
    headers = {'project_id': api_key}
    url = f'https://cardano-{NETWORK}.blockfrost.io/api/v0/txs/{txid}'
    response = requests.request('GET', url=url, headers=headers)
    return response.json()


if __name__ == '__main__':
    # TEST
    # stake_address = 'stake1uywz35vm9jyjzshs0trxnapmdpp6khscn68c7s0w8fqdlksrv4qgg'
    # print(get_balance_by_stake_address(stake_address))
    print(address_key_hash({"type": "PaymentVerificationKeyShelley_ed25519", "description": "Payment Verification Key",
                            "cborHex": "582072db109047ece86a7167c6329ceaf558bfc4c4c49997d718674d30dd1ca08857"}))
    pass
