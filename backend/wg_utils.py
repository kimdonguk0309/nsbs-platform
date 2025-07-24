from subprocess import run, PIPE

WG_INTERFACE_NAME = "wg0"
WG_PORT = 51820

def generate_wg_keypair():
    priv = run(["wg", "genkey"], stdout=PIPE, text=True).stdout.strip()
    pub = run(["wg", "pubkey"], input=priv, stdout=PIPE, text=True).stdout.strip()
    return priv, pub

def apply_wg_config(config_path):
    run(["wg-quick", "down", WG_INTERFACE_NAME], stdout=PIPE, stderr=PIPE)
    result = run(["wg-quick", "up", config_path], stdout=PIPE, stderr=PIPE, text=True)
    return result.stdout, result.stderr
