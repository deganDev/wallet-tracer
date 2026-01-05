from tracer.ports.chain_data_port import ChainDataPort
from tracer.core.dto import RawEthTransfer, RawErc20Transfer, TokenMeta
from typing import Optional, Dict, List

class StaticChainAdapter(ChainDataPort):
    def __init__(self, 
                 eth_transfers: Optional[List[RawEthTransfer]]=None,
                 erc20_transfers: Optional[List[RawErc20Transfer]]=None,
                 token_meta:Optional[Dict[str,TokenMeta]] = None,
                 contracts:Optional[Dict[str,bool]] = None,
                 ts_to_block: Optional[Dict[int, int]] = None,
                 ):
        self._eth = eth_transfers or []
        self._erc20 = erc20_transfers or []
        self._meta = token_meta or {}
        self._contract = {k.lower():v for k,v in (contracts or {}).items()}
        self._ts_to_block = ts_to_block or {}
    
    def get_block_number_by_time(self, unix_ts, closest:str = "before"):
        return self._ts_to_block.get(int(unix_ts), 0)
    
    def get_token_meta(self, token_address):
        return self._meta.get(token_address.lower(), TokenMeta(token_address, None, None, None))
    
    def iter_erc20_transfers(self, address, start_block, end_block, sort = "asc", token_address = None):
        ad = address.lower()
        token =  token_address.lower() if token_address else None
        items = [
           t for t in self._erc20
           if t.block_number >= start_block 
           and t.block_number <= end_block
           and (t.from_address.lower() == ad or t.to_address.lower() == ad)
           and (token is None or t.token_address.lower() == token)
        ]
        if sort=="desc":
            items.sort(key=lambda x: (x.block_number,x.timestamp),reverse=True)
        else:
            items.sort(key=lambda x: (x.block_number,x.timestamp))
        return items
    
    def iter_normal_txs(self, address, start_block, end_block, sort = "asc"):
        ad = address.lower()
        items = [
            t for t in self._eth
            if t.block_number >= start_block
            and t.block_number <= end_block
            and (t.from_address.lower() == ad or t.to_address.lower() == ad)
        ]
        if sort == "desc":
            items.sort(key=lambda x: (x.block_number,x.timestamp),reverse=True)
        else:
            items.sort(key=lambda x: (x.block_number,x.timestamp))
        return items
    
    def is_contract(self, address):
        return bool(self._contract.get(address.lower(), False))
