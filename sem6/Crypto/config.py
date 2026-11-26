"""
CryptoFlow Configuration Module
Defines ablation toggles, model hyperparameters, and dataset paths.
"""

import os

# --- Ablation Study Toggles ---
USE_MACROS = True
USE_WRAPPERS = True
USE_ALIASES = True

# --- Model Hyperparameters (v2) ---
CURVATURE = 1.0           # Curvature parameter (c) for Poincaré ball
NODE_FEATURE_DIM = 34     # Node feature vector dimension
HGNN_LAYERS = 3           # Number of hyperbolic graph conv layers
EMBEDDING_DIM = 256       # Hidden feature dimension
LEARNING_RATE = 0.001     # Optimizer learning rate
WEIGHT_DECAY = 1e-4       # Weight decay / regularization
DROPOUT = 0.2             # Dropout rate
NUM_EPOCHS = 300          # Training epochs
BATCH_SIZE = 8            # Batch size
PATIENCE = 30             # Early-stopping patience (epochs without val-loss improvement)

# --- Directory Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(BASE_DIR, "datasets")
GRAPHS_DIR = os.path.join(DATASETS_DIR, "interproc_graphs")
INTERPROC_STATS_PATH = os.path.join(DATASETS_DIR, "interproc_stats.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")
CHECKPOINTS_DIR = os.path.join(MODELS_DIR, "checkpoints")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
VISUALIZATIONS_DIR = os.path.join(BASE_DIR, "visualizations")

# Ensure critical directories exist
for directory in [GRAPHS_DIR, CHECKPOINTS_DIR, RESULTS_DIR, REPORTS_DIR, VISUALIZATIONS_DIR]:
    os.makedirs(directory, exist_ok=True)
