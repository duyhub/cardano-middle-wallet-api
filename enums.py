import os


def tryGetEnv(envname, elset):
    ENV_VAR = os.environ.get(envname)
    return (ENV_VAR != None and ENV_VAR) or elset


CARDANO_CLI_PATH = tryGetEnv("CARDANO_CLI_PATH", "cardano-cli")
"""
SET NETWORK
"""
# NETWORK = tryGetEnv("NETWORK", 'testnet')
NETWORK = 'mainnet'

TESTNET_MAGIC = tryGetEnv("TESTNET_MAGIC", "1097911063")

# Set blockfrost api according to network
api_blockfrost_mainnet = "<MAINNET BLOCKFROST API KEY>"
api_blockfrost_testnet = "<TESTNET BLOCKFROST API KEY>"
api_blockfrost = None
if NETWORK == 'mainnet':
    api_blockfrost = api_blockfrost_mainnet
elif NETWORK == 'testnet':
    api_blockfrost = api_blockfrost_testnet

BLOCKFROST_API_KEY = tryGetEnv("BLOCKFROST_API_KEY", api_blockfrost)

# Set CARDANO_NODE_SOCKET_PATH
# SOCKET_PATH = tryGetEnv("CARDANO_NODE_SOCKET_PATH", f"/Users/duy/cardano-src/{NETWORK}/node.socket")
SOCKET_PATH = f"/Users/duy/cardano-src/{NETWORK}/node.socket"
# SOCKET_PATH = tryGetEnv("SOCKET_PATH", '/ipc/node.socket')
my_env = os.environ.copy()
my_env["CARDANO_NODE_SOCKET_PATH"] = SOCKET_PATH
my_env["NETWORK"] = NETWORK
