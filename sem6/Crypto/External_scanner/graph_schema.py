"""
GraphSchema: Defines node types, edge types, feature schemas, and vector encodings
for CryptoFlow crypto-semantic graphs.
"""

from enum import Enum
from typing import Dict, List, Any


# --- Node Types ---
class NodeType(str, Enum):
    FILE = "FILE"
    FUNCTION = "FUNCTION"
    PARAMETER = "PARAMETER"
    VARIABLE = "VARIABLE"
    LITERAL = "LITERAL"
    KEY = "KEY"
    NONCE = "NONCE"
    CRYPTO_API = "CRYPTO_API"
    RANDOM_SOURCE = "RANDOM_SOURCE"
    WRAPPER = "WRAPPER"
    SINK = "SINK"


# --- Edge Types ---
class EdgeType(str, Enum):
    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
    ARGUMENT_TO_PARAMETER = "ARGUMENT_TO_PARAMETER"
    RETURNS_TO = "RETURNS_TO"
    ASSIGNED_FROM = "ASSIGNED_FROM"
    FLOWS_TO = "FLOWS_TO"
    ALIASES = "ALIASES"
    USES_AS_KEY = "USES_AS_KEY"
    USES_AS_NONCE = "USES_AS_NONCE"
    EXPOSES_TO = "EXPOSES_TO"


# --- Semantic Categoricals ---
class APISemanticRole(str, Enum):
    KEY = "key"
    NONCE = "nonce"
    ALGORITHM = "algorithm"
    PLAINTEXT = "plaintext"
    CIPHERTEXT = "ciphertext"
    CONTEXT = "context"


class SourceType(str, Enum):
    HARD_CODED = "hard_coded"
    RUNTIME = "runtime"
    RANDOM = "random"
    USER_INPUT = "user_input"


class SinkType(str, Enum):
    LOG = "log"
    NETWORK = "network"
    FILE = "file"
    MEMORY = "memory"


API_ROLES = ["unknown", "key", "nonce", "algorithm", "plaintext", "ciphertext", "iv", "hash"]
SOURCE_TYPES = ["unknown", "hard-coded", "runtime", "random", "user_input"]
SINK_TYPES = ["none", "crypto", "log", "network", "file", "memory"]

NODE_TYPE_LIST = [t.value for t in NodeType]
EDGE_TYPE_LIST = [t.value for t in EdgeType]

NODE_TYPE_TO_IDX: Dict[str, int] = {t: idx for idx, t in enumerate(NODE_TYPE_LIST)}
EDGE_TYPE_TO_IDX: Dict[str, int] = {t: idx for idx, t in enumerate(EDGE_TYPE_LIST)}
API_ROLE_TO_IDX: Dict[str, int] = {r: idx for idx, r in enumerate(API_ROLES)}
SOURCE_TYPE_TO_IDX: Dict[str, int] = {s: idx for idx, s in enumerate(SOURCE_TYPES)}
SINK_TYPE_TO_IDX: Dict[str, int] = {s: idx for idx, s in enumerate(SINK_TYPES)}

# Total feature dimensions:
# node_type (11) + api_role (8) + source_type (5) + sink_type (6) + [line_num_normalized, confidence, is_interproc_boundary, call_depth_normalized] = 34
NODE_FEATURE_DIM = len(NODE_TYPE_LIST) + len(API_ROLES) + len(SOURCE_TYPES) + len(SINK_TYPES) + 4
EDGE_FEATURE_DIM = len(EDGE_TYPE_LIST) + 2  # one-hot edge type + [param_index, confidence]


def encode_node_features(
    node_type: str,
    api_role: str = "unknown",
    source_type: str = "unknown",
    sink_type: str = "none",
    line_number: int = 1,
    confidence: float = 1.0,
    is_interproc_boundary: float = 0.0,
    call_depth_normalized: float = 0.0,
    max_lines: int = 1000,
) -> List[float]:
    """
    Encodes categorical and numerical node features into a float vector of length 34.
    """
    vec = [0.0] * NODE_FEATURE_DIM
    offset = 0

    # One-hot node_type (len=11)
    nt_idx = NODE_TYPE_TO_IDX.get(node_type, 0)
    vec[offset + nt_idx] = 1.0
    offset += len(NODE_TYPE_LIST)

    # One-hot api_role (len=8)
    role_idx = API_ROLE_TO_IDX.get(api_role, 0)
    vec[offset + role_idx] = 1.0
    offset += len(API_ROLES)

    # One-hot source_type (len=5)
    src_idx = SOURCE_TYPE_TO_IDX.get(source_type, 0)
    vec[offset + src_idx] = 1.0
    offset += len(SOURCE_TYPES)

    # One-hot sink_type (len=6)
    snk_idx = SINK_TYPE_TO_IDX.get(sink_type, 0)
    vec[offset + snk_idx] = 1.0
    offset += len(SINK_TYPES)

    # Numerical features (len=4):
    # offset + 0: normalized line number
    # offset + 1: confidence score
    # offset + 2: is_interproc_boundary (1.0 if function/call crosses file boundary)
    # offset + 3: call_depth_normalized (depth from file root / max_depth, index 33 in vec)
    vec[offset] = min(float(line_number) / max_lines, 1.0)
    vec[offset + 1] = float(confidence)
    vec[offset + 2] = float(is_interproc_boundary)
    vec[offset + 3] = min(max(float(call_depth_normalized), 0.0), 1.0)

    return vec


def encode_edge_features(
    edge_type: str,
    parameter_index: int = -1,
    confidence: float = 1.0,
) -> List[float]:
    """
    Encodes edge categorical and numerical features into a float vector.
    """
    vec = [0.0] * EDGE_FEATURE_DIM
    et_idx = EDGE_TYPE_TO_IDX.get(str(edge_type).upper(), 0)
    vec[et_idx] = 1.0
    vec[len(EDGE_TYPE_LIST)] = float(parameter_index)
    vec[len(EDGE_TYPE_LIST) + 1] = float(confidence)
    return vec
