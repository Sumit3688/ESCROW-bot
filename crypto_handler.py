import os
import logging
from typing import Dict
from web3 import Web3
from models import CryptoCurrency
from config import ADMIN_WALLETS

logger = logging.getLogger(__name__)

class CryptoHandler:
    def __init__(self):
        # Ethereum (for ETH)
        self.infura_url = os.environ.get("INFURA_URL", "https://mainnet.infura.io/v3/your_key")
        self.web3 = Web3(Web3.HTTPProvider(self.infura_url))

        # ✅ BSC (for USDT-BEP20)
        self.bsc_rpc_url = os.environ.get("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
        self.web3_bsc = Web3(Web3.HTTPProvider(self.bsc_rpc_url))

        # ✅ USDT BEP-20 contract on BSC
        self.usdt_contract_address_bsc = Web3.to_checksum_address(
            "0x55d398326f99059fF775485246999027B3197955"
        )

        self.min_confirmations = {
            CryptoCurrency.BITCOIN: 1,
            CryptoCurrency.ETHEREUM: 3,
            CryptoCurrency.USDT: 3,
        }

    async def generate_wallet(self, currency: CryptoCurrency) -> Dict[str, str]:
        if currency == CryptoCurrency.BITCOIN:
            return await self._generate_bitcoin_wallet()
        elif currency == CryptoCurrency.ETHEREUM:
            return await self._generate_ethereum_wallet()
        elif currency == CryptoCurrency.USDT:
            addr = ADMIN_WALLETS.get('USDT', 'not_configured')
            return {
                'address': addr,
                'private_key': 'EXTERNAL_MANAGED',
                'public_key': addr,
            }
        else:
            raise ValueError(f"Unsupported currency: {currency}")

    async def check_payment(self, address: str, expected_amount: float, currency: CryptoCurrency) -> bool:
        if currency == CryptoCurrency.USDT:
            return await self._check_usdt_payment_bsc(address, expected_amount)
        elif currency == CryptoCurrency.ETHEREUM:
            return await self._check_eth_payment(address, expected_amount)
        elif currency == CryptoCurrency.BITCOIN:
            return await self._check_btc_payment(address, expected_amount)
        else:
            return False

    async def _check_usdt_payment_bsc(self, address: str, expected_amount: float) -> bool:
        try:
            usdt_abi = [{
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            }]
            contract = self.web3_bsc.eth.contract(
                address=self.usdt_contract_address_bsc,
                abi=usdt_abi
            )
            bal_wei = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
            balance = bal_wei / (10 ** 18)  # ✅ BSC USDT has 18 decimals
            return balance >= float(expected_amount)
        except Exception as e:
            logger.error(f"USDT (BSC) check error: {e}")
            return False

    # NOTE: keep your existing BTC/ETH helper functions here
