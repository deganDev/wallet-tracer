from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional



# Configuration model

@dataclass(frozen=True)
class TraceConfig:
    """
    User input / run configuration for tracing.
    """

    address: str             
    days: int = 30              
    hops: int = 2                
    min_usd: Decimal | int | float = Decimal("0")

    # optional knobs (keep defaults sane)
    now_ts: Optional[int] = None
    max_edges_per_address: int = 0    # 0 = unlimited
    max_total_edges: int = 0          # 0 = unlimited



# Graph models

@dataclass
class Node:

    address: str
    is_contract: bool = False

    # Optional future fields
    # label: Optional[str] = None
    # risk_score: Optional[float] = None


@dataclass
class Edge:

    from_address: str
    to_address: str

    tx_hash: str
    timestamp: int

    asset_type: str            
    token_address: Optional[str] 
    symbol: Optional[str]       

    amount: Decimal
    usd_value: Optional[Decimal]


@dataclass
class Graph:

    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
