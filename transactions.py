from utils import *


def send_lovelace(sender_address, signing_key_path, recipient_address, lovelace, sender_cover_fee=True):
    # Tools: cardano-cli
    # Description: Send an amount of ADA from sender address to recipient_address
    #               with 2 modes which decide who will covers the network fee
    # Parameters:
    #           sender_address_path: payment address' path of sender
    #           sender_signing_key: signing key path
    #           recipient_address: address of recipient
    #           lovelace: amount of lovelace will be transferred ( 1 ADA = 1000000 lovelace)
    #           sender_cover_fee: True or False depends on who will pay the fee
    # Example:
    # If one wants to send 2 000 000 lovelace to an address, and the network fee is 200 000 lovelace.
    # sender_cover_fee = True --> payment_address's deducted 2 200 000, and recipient receives 2 000 000
    # sender_cover_fee = False --> payment_address's deducted 2 000 000, and recipient receives 1 800 000

    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    payment_address = sender_address

    # Query UTXO and read the output
    raw_utxo_table = None
    if NETWORK == 'mainnet':
        raw_utxo_table = subprocess.check_output([
            CARDANO_CLI_PATH, 'query', 'utxo',
            '--mainnet',
            '--address', payment_address], env=my_env)
    elif NETWORK == 'testnet':
        raw_utxo_table = subprocess.check_output([
            CARDANO_CLI_PATH, 'query', 'utxo',
            '--testnet-magic', TESTNET_MAGIC,
            '--address', payment_address], env=my_env)
    # print(raw_utxo_table[2])

    # Calculate total lovelace of the UTXO(s) inside the wallet address
    utxo_table_rows = raw_utxo_table.strip().splitlines()
    sum_lovelace_utxo = 0
    utxo_count = 0
    utxo_list = []
    for x in range(2, len(utxo_table_rows)):
        cells = utxo_table_rows[x].split()
        # If utxo includes a token -> skip
        if len(cells) > 6:
            continue

        utxo_list.append(cells[:3])
        sum_lovelace_utxo += int(cells[2])
        utxo_count += 1
        # Stop when txs' lovelace equals or exceeds the sending amount
        if sum_lovelace_utxo >= lovelace:
            break

    # Return if wallet's empty
    if utxo_count == 0:
        raise ValueError("The address is empty.")

    # Convert utf-8 to normal string
    for utxo in utxo_list:
        for i in range(len(utxo)):
            utxo[i] = utxo[i].decode('utf-8')

    # Build the transaction draft
    _id = get_unique_id()
    draft_path = f'transactions/tx_{_id}.draft'
    tx_in = []
    for utxo in utxo_list:
        tx_in += ['--tx-in', f'{utxo[0]}#{utxo[1]}']
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    try:
        if sender_cover_fee is True:
            build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build']
            build_parameters += tx_in
            build_parameters += ['--tx-out', f'{recipient_address}+{lovelace}', f'--change-address={payment_address}']
            build_parameters += net
            build_parameters += ['--out-file', draft_path,
                                 '--alonzo-era']
        else:
            build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build']
            build_parameters += tx_in
            build_parameters += ['--tx-out', f'{payment_address}+{sum_lovelace_utxo - lovelace}',
                                 f'--change-address={recipient_address}']
            build_parameters += net
            build_parameters += ['--out-file', draft_path, '--alonzo-era']
        subprocess.check_call(build_parameters, env=my_env)
    except subprocess.CalledProcessError:
        return False

    # Sign the transaction draft
    signed_path = f'transactions/tx_{_id}.signed'
    sign_parameters = [CARDANO_CLI_PATH, 'transaction', 'sign',
                       '--tx-body-file', draft_path,
                       '--signing-key-file', signing_key_path]
    sign_parameters += net
    sign_parameters += ['--out-file', signed_path]
    subprocess.check_call(sign_parameters, env=my_env)

    # Submit the transaction
    submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                         '--tx-file', signed_path]
    submit_parameters += net
    result = subprocess.check_output(submit_parameters, env=my_env)
    print(f'Send {lovelace} lovelace\nFrom: {payment_address}\nTo: {recipient_address}\n' +
          f'Sender covers fee: {sender_cover_fee}')
    print(result.decode('utf-8'))

    # Clean transaction building info
    try:
        os.remove(draft_path)
        os.remove(signed_path)
    except FileNotFoundError as e:
        print(f'send_lovelace: {e.errno}')
    return True


def send_all_remaining_lovelace(sender_address, signing_key_path, recipient_address):
    # Tools: cardano-cli
    # Description: Send all lovelace available in the sender address to recipient address.
    #              The recipient will cover network fee.
    # Parameters:
    #           sender_address_path: file path which stores sender's address
    #           signing_key_path: file path which stores sender's signing key
    #           recipient_address: destination address of the transaction

    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    payment_address = sender_address

    # Query UTXO and read the output
    raw_utxo_table = None
    if NETWORK == 'mainnet':
        raw_utxo_table = subprocess.check_output([
            CARDANO_CLI_PATH, 'query', 'utxo',
            '--mainnet',
            '--address', payment_address], env=my_env)
    elif NETWORK == 'testnet':
        raw_utxo_table = subprocess.check_output([
            CARDANO_CLI_PATH, 'query', 'utxo',
            '--testnet-magic', TESTNET_MAGIC,
            '--address', payment_address], env=my_env)
    # print(raw_utxo_table[2])

    # Calculate total lovelace of the UTXO(s) inside the wallet address
    utxo_table_rows = raw_utxo_table.strip().splitlines()
    sum_lovelace_utxo = 0
    utxo_count = 0
    utxo_list = []
    for x in range(2, len(utxo_table_rows)):
        cells = utxo_table_rows[x].split()
        # If utxo includes a token -> raise error and exit
        if len(cells) > 6:
            raise ValueError("There's at least 1 token inside the wallet. The wallet should have lovelace only.")
        utxo_list.append(cells[:3])
        sum_lovelace_utxo += int(cells[2])
        utxo_count += 1

    # Return if wallet's empty
    if utxo_count == 0:
        raise ValueError("The address is empty.")

    # Convert utf-8 to normal string
    for utxo in utxo_list:
        for i in range(len(utxo)):
            utxo[i] = utxo[i].decode('utf-8')

    # Build the transaction draft
    _id = get_unique_id()
    draft_path = f'transactions/tx_{_id}.draft'
    tx_in = []
    for utxo in utxo_list:
        tx_in += ['--tx-in', f'{utxo[0]}#{utxo[1]}']
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build']
    build_parameters += tx_in
    build_parameters += [
        f'--change-address={recipient_address}']
    build_parameters += net
    build_parameters += ['--out-file', draft_path, '--alonzo-era']
    subprocess.check_call(build_parameters, env=my_env)

    # Sign the transaction draft
    signed_path = f'transactions/tx_{_id}.signed'
    sign_parameters = [CARDANO_CLI_PATH, 'transaction', 'sign',
                       '--tx-body-file', draft_path,
                       '--signing-key-file', signing_key_path]
    sign_parameters += net
    sign_parameters += ['--out-file', signed_path]
    subprocess.check_call(sign_parameters, env=my_env)

    # Submit the transaction
    submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                         '--tx-file', signed_path]
    submit_parameters += net
    result = subprocess.check_output(submit_parameters, env=my_env)
    print(f'Send {sum_lovelace_utxo} lovelace\nFrom: {payment_address}\nTo: {recipient_address}'
          + '\nSender covers fee: False')
    print(result.decode('utf-8'))

    # Clean transaction building info
    try:
        os.remove(draft_path)
        os.remove(signed_path)
    except FileNotFoundError as e:
        print(f'send_all_remaining_lovelace: {e.errno}')
    return True


def refund_all_ada_utxos(payment_address, signing_key_path):
    # Description: Return all ADA utxos which have more than 2 ADA
    # Parameters:
    #           payment_address: payment address
    #           signing_key_path: path of signing key of payment address
    # Return:
    #       transaction id(s) of the refund transactions

    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    # Query UTXO and read the output
    raw_utxo_table = None
    if NETWORK == 'mainnet':
        raw_utxo_table = subprocess.check_output([
            CARDANO_CLI_PATH, 'query', 'utxo',
            '--mainnet',
            '--address', payment_address], env=my_env)
    elif NETWORK == 'testnet':
        raw_utxo_table = subprocess.check_output([
            CARDANO_CLI_PATH, 'query', 'utxo',
            '--testnet-magic', TESTNET_MAGIC,
            '--address', payment_address], env=my_env)
    # print(raw_utxo_table[2])

    utxo_list = []
    # Calculate total lovelace of the UTXO(s) inside the wallet address
    utxo_table_rows = raw_utxo_table.strip().splitlines()
    for x in range(2, len(utxo_table_rows)):
        cells = utxo_table_rows[x].split()
        # If utxo includes a token or lovelace < 2 000 000 -> skip
        if len(cells) > 6 or int(cells[2].decode('utf-8')) < 2000000:
            continue
        utxo_list.append(cells[:3])

    for utxo in utxo_list:
        for i in range(len(utxo)):
            utxo[i] = utxo[i].decode('utf-8')

    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    txid_list = []
    signed_path = ''
    draft_path = ''
    for utxo in utxo_list:
        tx = get_transaction_content(utxo[0])
        sender_utxo_address = tx['inputs'][0]['address']
        print(sender_utxo_address)

        # Build the transaction
        _id = get_unique_id()
        draft_path = f'transactions/tx_{_id}.draft'
        build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build']
        build_parameters += ['--tx-in', f'{utxo[0]}#{utxo[1]}']
        build_parameters += [f'--change-address={sender_utxo_address}']
        build_parameters += net
        build_parameters += ['--out-file', draft_path, '--alonzo-era']
        try:
            subprocess.check_call(build_parameters, env=my_env)
        except subprocess.CalledProcessError:
            raise ValueError('refund_all_ada_utxos: Error in building transaction step')

        # Sign the transaction draft
        signed_path = f'transactions/tx_{_id}.signed'
        sign_parameters = [CARDANO_CLI_PATH, 'transaction', 'sign',
                           '--tx-body-file', draft_path,
                           '--signing-key-file', signing_key_path]
        sign_parameters += net
        sign_parameters += ['--out-file', signed_path]
        try:
            subprocess.check_call(sign_parameters, env=my_env)
        except subprocess.CalledProcessError:
            raise ValueError('refund_all_ada_utxos: Error in signing transaction step')

        # Submit the transaction
        submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                             '--tx-file', signed_path]
        submit_parameters += net
        try:
            result = subprocess.check_output(submit_parameters, env=my_env)
        except subprocess.CalledProcessError:
            raise ValueError('refund_all_ada_utxos: Error in submit transaction step')

        print(f'Send {utxo[2]} lovelace\nFrom: {payment_address}\nTo: {sender_utxo_address}'
              + '\nSender covers fee: False')
        print(result.decode('utf-8'))

        # Record the txid
        txid_parameters = [CARDANO_CLI_PATH, 'transaction', 'txid', '--tx-file', signed_path]
        txid_list.append(subprocess.check_output(txid_parameters, env=my_env))

    json_txid = []
    for txid in txid_list:
        json_txid.append({'txid': txid.decode('utf-8').strip('\n')})

    try:
        os.remove(signed_path)
        os.remove(draft_path)
    except FileNotFoundError as e:
        print(f'refund_all_ada_utxos: {e.errno}')
    return json_txid


def return_all_utxos(payment_address, signing_key_path):
    # Description: return all both ADA and non-ADA utxos in the payment address to its original owner
    # Requirement: unless the wallet has non-asset utxo containing equal or more than 2 ADA to cover network fee,
    #               the method will raise error

    # Make directory
    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    # Set network
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    # Query utxo
    utxo_list = query_utxos(payment_address)

    # Find sender address
    from_address = [''] * len(utxo_list)
    for i, utxo in enumerate(utxo_list):
        tx = get_transaction_content(utxo[0])
        sender_utxo_address = tx['inputs'][0]['address']
        from_address[i] = sender_utxo_address

    # Build transaction
    _id = get_unique_id()
    draft_path = f'transactions/tx_{_id}.draft'
    build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build']

    # tx-in
    for utxo in utxo_list:
        build_parameters += ['--tx-in', f'{utxo[0]}#{utxo[1]}']

    # tx-out
    cover_utxo_address = ''
    for i, utxo in enumerate(utxo_list):
        if len(utxo) <= 6 and int(utxo[2]) >= 2000000 and cover_utxo_address == '':
            cover_utxo_address = from_address[i]
            continue
        if len(utxo) <= 6:
            build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}']
        else:
            build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}'
                                             f'+{utxo[5]} {utxo[6]}']

    # # Raise error if there's not enough fund to cover network fee
    # if cover_utxo_address == '':
    #     raise ValueError(f'refund_all_utxos: Not enough fund to cover network fee. '
    #                      f'Need at least 1 ADA-only utxo containing equal or more than 2 ADA.')

    # return empty list if there's not enough fund to cover network fee
    if cover_utxo_address == '':
        print('refund_all_utxos: Not enough fund to cover network fee. Need at least a 2-ADA utxo')
        return []

    # change-address
    build_parameters += ['--change-address', cover_utxo_address]

    build_parameters += net
    build_parameters += ['--out-file', draft_path, '--alonzo-era']
    try:
        subprocess.check_call(build_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('refund_all_utxos: Error in building transaction')

    # Sign the transaction draft
    signed_path = f'transactions/tx_{_id}.signed'
    sign_parameters = [CARDANO_CLI_PATH, 'transaction', 'sign',
                       '--tx-body-file', draft_path,
                       '--signing-key-file', signing_key_path]
    sign_parameters += net
    sign_parameters += ['--out-file', signed_path]
    try:
        subprocess.check_call(sign_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('refund_all_utxos: Error in signing transaction')

    # Submit the transaction
    submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                         '--tx-file', signed_path]
    submit_parameters += net
    try:
        result = subprocess.check_output(submit_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('refund_all_utxos: Error at submit transaction step.')
    print(result.decode('utf-8'))

    # Record the txid
    txid_parameters = [CARDANO_CLI_PATH, 'transaction', 'txid', '--tx-file', signed_path]
    try:
        txid = subprocess.check_output(txid_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('refund_all_utxos: Error at getting outgoing txid')
    txid = [{'txid': txid.decode('utf-8').strip('\n')}]

    # Clean transaction files
    try:
        os.remove(signed_path)
        os.remove(draft_path)
    except FileNotFoundError as e:
        print(f'refund_all_utxos: {e.errno}')

    return txid


def return_all_registered_utxos(payment_address, signing_key_path, stake_list):
    # Description: return all registered utxos in the payment address to its original owner
    # Requirement: unless the wallet has non-asset utxo containing equal or more than 2 ADA to cover network fee,
    #               the method will raise error

    # Make directory
    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    # Set network
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    # Query utxo
    utxo_list = query_utxos(payment_address)

    # Find sender address
    utxo_mark = [0] * len(utxo_list)
    from_address = [''] * len(utxo_list)
    for i, utxo in enumerate(utxo_list):
        tx = get_transaction_content(utxo[0])
        sender_utxo_address = tx['inputs'][0]['address']
        sender_stake_address = get_stake_address(sender_utxo_address)
        if sender_stake_address in stake_list:
            utxo_mark[i] = 1
            from_address[i] = sender_utxo_address

    txid = []
    # Build transaction
    _id = get_unique_id()
    draft_path = f'transactions/tx_{_id}.draft'
    build_parameters = [CARDANO_CLI_PATH, 'transaction', 'build']

    # tx-in
    for i, utxo in enumerate(utxo_list):
        if utxo_mark[i] == 1:
            build_parameters += ['--tx-in', f'{utxo[0]}#{utxo[1]}']

    # tx-out
    cover_utxo_address = ''
    for i, utxo in enumerate(utxo_list):
        if utxo_mark[i] == 1:
            print(i)
            if len(utxo) <= 6 and int(utxo[2]) >= 2000000 and cover_utxo_address == '':
                cover_utxo_address = from_address[i]
                continue
            if len(utxo) <= 6:
                build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}']
            else:
                build_parameters += ['--tx-out', f'{from_address[i]}+{utxo[2]}'
                                                 f'+{utxo[5]} {utxo[6]}']
    if cover_utxo_address == '':
        print('refund_all_utxos: Not enough fund to cover network fee.')
        return []
        # raise ValueError(f'refund_all_registered_utxos: Not enough fund to cover network fee. '
        #                  f'Need at least 1 ADA-only utxo containing equal or more than 2 ADA.')
    # change-address
    build_parameters += ['--change-address', cover_utxo_address]

    build_parameters += net
    build_parameters += ['--out-file', draft_path, '--alonzo-era']
    try:
        subprocess.check_call(build_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('refund_all_registered_utxos: Error in building transaction')

    # Sign the transaction draft
    signed_path = f'transactions/tx_{_id}.signed'
    sign_parameters = [CARDANO_CLI_PATH, 'transaction', 'sign',
                       '--tx-body-file', draft_path,
                       '--signing-key-file', signing_key_path]
    sign_parameters += net
    sign_parameters += ['--out-file', signed_path]
    try:
        subprocess.check_call(sign_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('refund_all_registered_utxos: Error in signing transaction')

    # Submit the transaction
    submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                         '--tx-file', signed_path]
    submit_parameters += net
    try:
        result = subprocess.check_output(submit_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('refund_all_registered_utxos: Error at submit transaction step. Possibly wrong signing key')
    print(result.decode('utf-8'))

    # Record the txid
    txid_parameters = [CARDANO_CLI_PATH, 'transaction', 'txid', '--tx-file', signed_path]
    try:
        txid = subprocess.check_output(txid_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('refund_all_registered_utxos: Error at getting outgoing txid')
    txid = [{'txid': txid.decode('utf-8').strip('\n')}]

    # Clean transaction files
    try:
        os.remove(signed_path)
        os.remove(draft_path)
    except FileNotFoundError as e:
        print(f'refund_all_registered_utxos: {e.errno}')

    return txid


def get_transaction_body(sender_stake_address, package):
    """
    Send ADA from one address to multiple addresses in one transaction
    :param sender_stake_address:
    :param package:
    :return: response
    """
    response = {
        'input': [],
        'output': []
    }

    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    # Choose network
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    # Create protocol.json
    protocol_path = get_protocol_file_path()

    # Calculate total amount of ADA and assets needed to send
    package_balance = {}
    for p in package:
        each_package = {}
        for a in p['amount']:
            if a['unit'] in each_package:
                each_package[a['unit']] += int(a['quantity'])
            else:
                each_package[a['unit']] = int(a['quantity'])
            if a['unit'] in package_balance:
                package_balance[a['unit']] += int(a['quantity'])
            else:
                package_balance[a['unit']] = int(a['quantity'])
        p['amount'] = each_package
    print(package)
    print('Package summary:')
    for key in package_balance:
        print(f'unit: {key}\nquantity: {package_balance[key]} ')

    # Check if the sender wallet has enough funds and assets to send
    response_list = get_address_list_by_stake_address(sender_stake_address)
    print(f'response_list: {response_list}')
    sender_address_list = []
    for address in response_list:
        sender_address_list.append(address['address'])
    sender_address = sender_address_list[0]

    utxo_list = []
    for address in sender_address_list:
        utxo_list += query_utxos(address)

    sender_balance = {}
    for utxo in utxo_list:
        sender_balance = add_utxo_to_dict(sender_balance, utxo)

    print('-' * 20)
    print("Sender balance:")
    for key in sender_balance:
        print(f'unit: {key}\nquantity: {sender_balance[key]} ')
    print('-' * 20)
    for key in package_balance:
        if key not in sender_balance:
            return {'error': 'The number of assets/ADA in the wallet cannot afford the transaction.'}
        if package_balance[key] > sender_balance[key]:
            return {'error': 'The number of assets/ADA in the wallet cannot afford the transaction.'}

    # Set tx-out utxos to recipients
    package_lovelace_req = 0
    txout_list = []
    for p in package:
        txout_records = []
        amount_records = []
        amount = p['amount']
        for key in amount:
            txout_records.append(f'{amount[key]} {key}')
            amount_records.append({
                'unit': key,
                'quantity': f'{amount[key]}'
            })
        tx_out = f"{p['address']}+{'+'.join(txout_records)}"
        min_lovelace = calculate_min_required_utxo(tx_out)
        if int(min_lovelace) > 1000000:
            txout_records = []
            amount_records = []
            if 'lovelace' in amount:
                amount['lovelace'] += int(min_lovelace)
            else:
                amount['lovelace'] = int(min_lovelace)
            for key in amount:
                txout_records.append(f'{amount[key]} {key}')
                amount_records.append({
                    'unit': key,
                    'quantity': f'{amount[key]}'
                })
            tx_out = f"{p['address']}+{'+'.join(txout_records)}"

        # print(tx_out)
        txout_list.append(tx_out)
        response['output'].append({
            'address': p['address'],
            'amount': amount_records
        })
        package_lovelace_req += amount['lovelace']

    # Update lovelace for package_balance
    package_balance['lovelace'] = package_lovelace_req

    print('tx-out to recipients')
    print(txout_list)
    print('-' * 20)
    if int(sender_balance['lovelace']) < package_lovelace_req:
        return {'error': 'get_transaction_body: Not enough lovelace.'}

    # Set tx-in utxos
    # utxo_list_bf = sorted(utxo_list_bf, key=len)
    mark_list = [0] * len(utxo_list)
    temp = {}
    txin_list = []
    fee = 0
    for i, utxo in enumerate(utxo_list):
        print(f'utxo: {utxo}')
        temp = add_utxo_to_dict(temp, utxo)
        mark_list[i] = 1
        txin_list.append(f'{utxo[0]}#{utxo[1]}')
        response['input'].append({'txhash': utxo[0], 'index': utxo[1]})
        if check_enough_fund(temp, package_balance):
            # Calculate remaining asset/ADA for utxos marked
            change_list = temp.copy()
            for key in package_balance:
                change_list[key] -= int(package_balance[key])

            # Calculate minimum lovelace required for utxo sending back to sender
            txout_records = []
            amount_records = []
            for key in change_list:
                if change_list[key] > 0:
                    txout_records.append(f'{change_list[key]} {key}')
                    amount_records.append({
                        'unit': key,
                        'quantity': f'{change_list[key]}'
                    })
            tx_out = f"{sender_address}+{'+'.join(txout_records)}"
            if len(txout_records) > 0:
                min_lovelace = calculate_min_required_utxo(tx_out)
            else:
                min_lovelace = 0
            if 0 < min_lovelace <= change_list['lovelace']:
                # Add fee and check again
                # txout_list.append(tx_out)
                # response['output'].append({
                #     'address': sender_address,
                #     'amount': amount_records
                # })
                # print(f'txin_list: {txin_list}')
                # print(f'txout_list: {txout_list}')
                fee = calculate_fee(txin_list, txout_list, protocol_path)

                # If have enough ADA to cover fee -> proceed
                if change_list['lovelace'] - fee >= min_lovelace:
                    change_list['lovelace'] -= fee
                    txout_records = []
                    amount_records = []
                    for key in change_list:
                        if change_list[key] > 0:
                            txout_records.append(f'{change_list[key]} {key}')
                            amount_records.append({
                                'unit': key,
                                'quantity': f'{change_list[key]}'
                            })
                    # txout_records = [f'{change_list[key]} {key}' for key in change_list if change_list[key] > 0]
                    tx_out = f"{sender_address}+{'+'.join(txout_records)}"

                    # Add tx_out to txout_list
                    txout_list.append(tx_out)
                    response['output'].append({
                        'address': sender_address,
                        'amount': amount_records
                    })
                    break
        if i == len(utxo_list) - 1:
            return {'error': 'get_transaction_body: Not enough lovelace to cover fees.'}

    # Print tx-in and tx-out
    print('\n\ntx-in')
    for tx in txin_list:
        print(tx)
    print('\n\ntxout')
    for tx in txout_list:
        print(tx)
    print(f'fee: {fee}\n')

    response['fee'] = str(fee)
    return response


def sign_and_submit_transaction(draft_path, signing_key_path, _id):
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    # Create transaction path
    if not os.path.isdir('transactions'):
        os.makedirs('transactions')

    # Sign
    signed_path = f'transactions/tx_{_id}.signed'
    sign_parameters = [CARDANO_CLI_PATH, 'transaction', 'sign',
                       '--tx-body-file', draft_path,
                       '--signing-key-file', signing_key_path]
    sign_parameters += net
    sign_parameters += ['--out-file', signed_path]
    try:
        subprocess.check_call(sign_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('sign_and_submit_transaction: Error in signing transaction')

    # Submit
    submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                         '--tx-file', signed_path]
    submit_parameters += net

    try:
        result = subprocess.check_output(submit_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('sign_and_submit_transaction: Error at submit transaction step.')
    print(result.decode('utf-8'))

    # Record the txid
    txid_parameters = [CARDANO_CLI_PATH, 'transaction', 'txid', '--tx-file', signed_path]
    try:
        txid = subprocess.check_output(txid_parameters, env=my_env)
    except subprocess.CalledProcessError:
        raise ValueError('sign_and_submit_transaction: Error at getting outgoing txid')

    # Clean files
    try:
        os.remove(signed_path)
    except FileNotFoundError:
        raise ValueError('sign_and_submit_transaction: File not found while cleaning files')
    return txid.decode('utf-8').strip('\n')


def submit_transaction(signed_path):
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    submit_parameters = [CARDANO_CLI_PATH, 'transaction', 'submit',
                         '--tx-file', signed_path]
    submit_parameters += net

    try:
        result = subprocess.check_output(submit_parameters, env=my_env)
    except subprocess.CalledProcessError as e:
        raise ValueError('submit_transaction: Error when submit transaction')
        # return {'error': e.stderr}
    print(result.decode('utf-8'))

    # Record the txid
    txid_parameters = [CARDANO_CLI_PATH, 'transaction', 'txid', '--tx-file', signed_path]
    try:
        txid = subprocess.check_output(txid_parameters, env=my_env)
    except subprocess.CalledProcessError as e:
        raise ValueError('submit_transaction: Error at getting transaction id')

    return txid.decode('utf-8').strip('\n')


def get_txid(signed_path):
    net = None
    if NETWORK == 'mainnet':
        net = ['--mainnet']
    elif NETWORK == 'testnet':
        net = ['--testnet-magic', str(TESTNET_MAGIC)]

    txid_parameters = [CARDANO_CLI_PATH, 'transaction', 'txid', '--tx-file', signed_path]

    txid = run_command(txid_parameters, my_env)
    if type(txid) is subprocess.CalledProcessError:
        raise txid

    return txid.decode('utf-8').strip('\n')
