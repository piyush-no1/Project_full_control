import os
import json
from typing import List, Tuple

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from keras import layers

BASE_GESTURES: List[str] = [
    "scroll_up",
    "scroll_down",
    "swipe_right",
    "swipe_left",
    "zoom_in",
    "zoom_out",
    "volume_up",
    "volume_down",
    "play/pause",
]

FEATURE_STATS_DEFAULT_PATH = "models/feature_stats.json"


def _ensure_parent_dir(path: str) -> None:
    dirpath = os.path.dirname(path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)


# ============================================================
# Feature engineering
# ============================================================

def _compute_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Compute angle at point b formed by a-b-c. Returns radians [0, pi]."""
    v1 = a - b
    v2 = c - b
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 < 1e-6 or norm2 < 1e-6:
        return 0.0
    cosang = float(np.dot(v1, v2) / (norm1 * norm2 + 1e-8))
    cosang = np.clip(cosang, -1.0, 1.0)
    return float(np.arccos(cosang))


def _compute_finger_curl(pts: np.ndarray) -> np.ndarray:
    """
    Finger curl ratio: (tip-to-mcp distance) / (total bone length).
    0 = fully curled, 1 = fully extended.
    Returns 5 values (thumb, index, middle, ring, pinky).
    """
    fingers = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
        [13, 14, 15, 16],
        [17, 18, 19, 20],
    ]
    curls = []
    for mcp, pip, dip, tip in fingers:
        bone_len = (
            np.linalg.norm(pts[pip] - pts[mcp])
            + np.linalg.norm(pts[dip] - pts[pip])
            + np.linalg.norm(pts[tip] - pts[dip])
        )
        direct_dist = np.linalg.norm(pts[tip] - pts[mcp])
        if bone_len < 1e-6:
            curls.append(0.0)
        else:
            curls.append(float(direct_dist / bone_len))
    return np.array(curls, dtype="float32")


def _compute_fingertip_distances(pts: np.ndarray) -> np.ndarray:
    """
    Key pairwise distances that matter for gesture discrimination:
    - thumb-index (pinch detection)
    - thumb-middle
    - thumb-pinky (spread detection)
    - index-middle (V sign detection)
    - index-pinky (spread detection)
    Returns 5 distances.
    """
    pairs = [(4, 8), (4, 12), (4, 20), (8, 12), (8, 20)]
    distances = []
    for i, j in pairs:
        d = np.linalg.norm(pts[i] - pts[j])
        distances.append(d)
    return np.array(distances, dtype="float32")


def engineer_hand_features(X: np.ndarray) -> np.ndarray:
    """
    Optimized feature engineering for ~1350 samples per class.

    Features (total 40 dimensions):
      1. Fingertip + key joint positions relative to wrist, normalized (30)
         - Only tips (4,8,12,16,20) and MCP joints (1,5,9,13,17) = 10 points × 3 coords
         - Removes redundant intermediate joints that add noise
      2. Finger curl ratios (5) — robust gesture discriminator
      3. Key fingertip pairwise distances (5) — pinch/spread detection

    Input:  X: (N, 63) raw landmarks
    Output: X_eng: (N, 40) engineered features
    """
    if X.ndim != 2 or X.shape[1] != 63:
        raise ValueError(f"Expected X shape (N, 63), got {X.shape}")

    N = X.shape[0]
    coords = X.reshape(N, 21, 3)

    # Wrist-centering
    wrist = coords[:, 0:1, :]
    rel = coords - wrist

    # Scale normalization
    dists = np.linalg.norm(rel, axis=2)
    max_dist = np.max(dists, axis=1, keepdims=True)
    max_dist[max_dist < 1e-6] = 1.0
    rel_norm = rel / max_dist[:, :, None]

    # Key landmark indices: MCPs + fingertips only (skip PIP, DIP — they add noise)
    # MCP: 1 (thumb CMC), 5, 9, 13, 17
    # Tips: 4, 8, 12, 16, 20
    key_indices = [1, 5, 9, 13, 17, 4, 8, 12, 16, 20]

    # Extract key positions: (N, 10, 3) -> (N, 30)
    key_positions = rel_norm[:, key_indices, :].reshape(N, -1).astype("float32")

    # Finger curls and distances
    curl_features = np.zeros((N, 5), dtype="float32")
    distance_features = np.zeros((N, 5), dtype="float32")

    for i in range(N):
        pts = rel_norm[i]
        curl_features[i] = _compute_finger_curl(pts)
        distance_features[i] = _compute_fingertip_distances(pts)

    # Concatenate: 30 + 5 + 5 = 40 features
    X_eng = np.concatenate(
        [key_positions, curl_features, distance_features],
        axis=1,
    )

    return X_eng


# ============================================================
# Feature stats (standardization)
# ============================================================

def _fit_and_save_feature_stats(
    X: np.ndarray,
    feature_stats_path: str = FEATURE_STATS_DEFAULT_PATH,
) -> Tuple[np.ndarray, np.ndarray]:
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std < 1e-6] = 1.0

    _ensure_parent_dir(feature_stats_path)
    stats = {"mean": mean.tolist(), "std": std.tolist()}
    with open(feature_stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    return mean.astype("float32"), std.astype("float32")


def load_feature_stats(
    feature_stats_path: str = FEATURE_STATS_DEFAULT_PATH,
) -> Tuple[np.ndarray, np.ndarray]:
    if not os.path.exists(feature_stats_path):
        print(f"[ModelTrainer] Feature stats file '{feature_stats_path}' not found.")
        return None, None

    with open(feature_stats_path, "r", encoding="utf-8") as f:
        stats = json.load(f)

    mean = np.array(stats["mean"], dtype="float32")
    std = np.array(stats["std"], dtype="float32")
    std[std < 1e-6] = 1.0
    return mean, std


# ============================================================
# Minimal data augmentation (scaling only, no rotation)
# ============================================================

def augment_landmarks(
    X_raw: np.ndarray,
    labels: np.ndarray,
    augment_factor: int = 2,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Minimal augmentation for 1350 samples/class:
    - Small random scaling (0.92–1.08) to simulate distance variation.
    - NO rotation (hand orientation matters for gesture identity).
    - NO noise (1350 samples is sufficient; noise can blur gesture boundaries).

    Input:
      X_raw: (N, 63) raw landmarks
      labels: (N,) string labels
      augment_factor: augmented copies per original (default 2 → total 3x)

    Output:
      X_aug: (N * (1 + augment_factor), 63)
      labels_aug: same length
    """
    N = X_raw.shape[0]
    all_X = [X_raw]
    all_labels = [labels]

    for _ in range(augment_factor):
        X_copy = X_raw.copy().reshape(N, 21, 3)

        # Small random scaling only
        scales = np.random.uniform(0.92, 1.08, (N, 1, 1)).astype("float32")
        wrists = X_copy[:, 0:1, :]
        X_copy = (X_copy - wrists) * scales + wrists

        all_X.append(X_copy.reshape(N, 63))
        all_labels.append(labels.copy())

    X_aug = np.vstack(all_X)
    labels_aug = np.concatenate(all_labels)

    return X_aug, labels_aug


# ============================================================
# Data loading
# ============================================================

def _prepare_dataset_from_dir(
    data_dir: str,
    label_map_path: str,
    feature_stats_path: str,
    augment: bool = True,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"Data directory '{data_dir}' not found.")

    csv_files = [
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.lower().endswith(".csv")
    ]
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in directory '{data_dir}'."
        )

    all_features = []
    all_labels: List[str] = []
    feature_cols_ref = None

    for csv_path in sorted(csv_files):
        gesture_name = os.path.splitext(os.path.basename(csv_path))[0]
        df = pd.read_csv(csv_path)

        if "label" in df.columns:
            df = df.drop(columns=["label"])

        if feature_cols_ref is None:
            feature_cols_ref = [c for c in df.columns if c.startswith("f")]
            if not feature_cols_ref:
                feature_cols_ref = df.columns.tolist()

        feature_cols = [c for c in feature_cols_ref if c in df.columns]
        if len(feature_cols) != len(feature_cols_ref):
            raise ValueError(
                f"Inconsistent feature columns in '{csv_path}'."
            )

        X_file = df[feature_cols].values.astype("float32")

        # Remove NaN/Inf rows
        valid_mask = np.all(np.isfinite(X_file), axis=1)
        X_file = X_file[valid_mask]

        all_features.append(X_file)
        all_labels.extend([gesture_name] * len(X_file))

        print(
            f"[ModelTrainer] Loaded {len(X_file)} samples for "
            f"'{gesture_name}' from '{csv_path}'."
        )

    if not all_features:
        raise ValueError("No gesture data arrays were loaded from CSV files.")
    if all(x.shape[0] == 0 for x in all_features):
        raise ValueError(
            "No valid finite samples found after filtering NaN/Inf rows."
        )

    X_raw = np.vstack(all_features)
    labels = np.array(all_labels, dtype=str)

    # Print class distribution
    unique, counts = np.unique(labels, return_counts=True)
    print("\n[ModelTrainer] Class distribution:")
    for u, c in zip(unique, counts):
        print(f"  {u}: {c} samples")

    # Check for class imbalance
    min_count = min(counts)
    max_count = max(counts)
    if max_count > 2 * min_count:
        print(
            f"\n[ModelTrainer] WARNING: Class imbalance detected "
            f"(min={min_count}, max={max_count}). "
            "Consider collecting more data for smaller classes."
        )

    # Augmentation
    if augment:
        print("\n[ModelTrainer] Augmenting data (scaling only)...")
        X_raw, labels = augment_landmarks(X_raw, labels, augment_factor=2)
        print(f"[ModelTrainer] After augmentation: {len(X_raw)} total samples")
    if len(X_raw) == 0:
        raise ValueError("No samples available for training after preprocessing.")

    # Build label map
    label_list = sorted(set(labels))
    num_classes = len(label_list)
    if num_classes < 2:
        raise ValueError(
            f"Need at least 2 classes, found {num_classes}: {label_list}"
        )

    label_to_index = {name: i for i, name in enumerate(label_list)}
    indices = np.array([label_to_index[lab] for lab in labels], dtype="int32")
    y = keras.utils.to_categorical(indices, num_classes=num_classes)

    # Save label map
    _ensure_parent_dir(label_map_path)
    with open(label_map_path, "w", encoding="utf-8") as f:
        json.dump(label_list, f, indent=2)

    # Feature engineering + standardization
    X_eng = engineer_hand_features(X_raw)
    mean, std = _fit_and_save_feature_stats(X_eng, feature_stats_path)
    X_std = (X_eng - mean) / std

    # Shuffle
    shuffle_idx = np.random.permutation(len(X_std))
    X_std = X_std[shuffle_idx]
    y = y[shuffle_idx]

    return X_std.astype("float32"), y.astype("float32"), label_list


def _prepare_dataset_from_file(
    csv_path: str,
    label_map_path: str,
    feature_stats_path: str,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset CSV not found at '{csv_path}'.")

    df = pd.read_csv(csv_path)
    if "label" not in df.columns:
        raise ValueError("CSV must contain a 'label' column.")

    feature_cols = [c for c in df.columns if c != "label"]
    if len(feature_cols) == 0:
        raise ValueError("CSV must contain feature columns.")

    X_raw = df[feature_cols].values.astype("float32")
    labels = df["label"].astype(str).values

    valid_mask = np.all(np.isfinite(X_raw), axis=1)
    X_raw = X_raw[valid_mask]
    labels = labels[valid_mask]
    if len(X_raw) == 0:
        raise ValueError(
            "No valid finite samples found in dataset CSV after filtering."
        )

    X_raw, labels = augment_landmarks(X_raw, labels, augment_factor=2)
    if len(X_raw) == 0:
        raise ValueError("No samples available for training after augmentation.")

    label_list = sorted(set(labels))
    num_classes = len(label_list)
    if num_classes == 0:
        raise ValueError("No labels found.")

    label_to_index = {name: i for i, name in enumerate(label_list)}
    indices = np.array([label_to_index[lab] for lab in labels], dtype="int32")
    y = keras.utils.to_categorical(indices, num_classes=num_classes)

    _ensure_parent_dir(label_map_path)
    with open(label_map_path, "w", encoding="utf-8") as f:
        json.dump(label_list, f, indent=2)

    X_eng = engineer_hand_features(X_raw)
    mean, std = _fit_and_save_feature_stats(X_eng, feature_stats_path)
    X_std = (X_eng - mean) / std

    shuffle_idx = np.random.permutation(len(X_std))
    X_std = X_std[shuffle_idx]
    y = y[shuffle_idx]

    return X_std.astype("float32"), y.astype("float32"), label_list


def _prepare_dataset(
    data_path: str,
    label_map_path: str,
    feature_stats_path: str,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    if os.path.isdir(data_path):
        return _prepare_dataset_from_dir(data_path, label_map_path, feature_stats_path)
    if os.path.isfile(data_path):
        return _prepare_dataset_from_file(data_path, label_map_path, feature_stats_path)

    parent_dir = os.path.dirname(data_path)
    if parent_dir and os.path.isdir(parent_dir):
        return _prepare_dataset_from_dir(parent_dir, label_map_path, feature_stats_path)

    raise FileNotFoundError(
        f"Data path '{data_path}' is neither a file nor a directory."
    )


# ============================================================
# Model — right-sized for ~1350 samples × 9 classes
# ============================================================

def build_model(num_classes: int, input_dim: int = 40) -> keras.Model:
    """
    Right-sized model for ~1350 samples/class with 40 features.

    Architecture:
      Input(40)
        -> Dense(128, relu) + BatchNorm + Dropout(0.3)
        -> Dense(64, relu)  + BatchNorm + Dropout(0.2)
        -> Dense(32, relu)
        -> Dense(num_classes, softmax)

    Not too deep (avoids overfitting on ~12K total samples).
    Not too shallow (enough capacity for 9+ classes).
    """
    inputs = keras.Input(shape=(input_dim,))

    x = layers.Dense(128, activation="relu",
                     kernel_regularizer=keras.regularizers.l2(1e-4))(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)

    x = layers.Dense(64, activation="relu",
                     kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.2)(x)

    x = layers.Dense(32, activation="relu")(x)

    outputs = layers.Dense(num_classes, activation="softmax")(x)

    model = keras.Model(inputs=inputs, outputs=outputs)

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


# ============================================================
# Training
# ============================================================

def train_model(
    csv_path: str = "data",
    model_output_path: str = "models/gesture_ann.keras",
    label_map_path: str = "models/label_map.json",
    feature_stats_path: str = FEATURE_STATS_DEFAULT_PATH,
    epochs: int = 50,
    batch_size: int = 32,
    validation_split: float = 0.2,
) -> keras.Model:
    """
    Train gesture classifier.

    Optimized for ~1350 samples/class × 9 classes:
      - 40 clean features (no noise from redundant joints)
      - 2x scaling augmentation → ~36K total samples
      - Right-sized 3-layer model (128→64→32)
      - batch_size=32 (better gradients for this data size)
      - Early stopping + LR reduction
    """
    print("[ModelTrainer] Preparing dataset...")
    X, y, label_list = _prepare_dataset(csv_path, label_map_path, feature_stats_path)
    num_classes = len(label_list)

    print(
        f"\n[ModelTrainer] Final dataset: {X.shape[0]} samples, "
        f"{X.shape[1]} features, {num_classes} classes"
    )
    print(f"[ModelTrainer] Classes: {label_list}\n")

    model = build_model(num_classes=num_classes, input_dim=X.shape[1])
    model.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=8,
            restore_best_weights=True,
            verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=4,
            min_lr=1e-6,
            verbose=1,
        ),
    ]

    print("\n[ModelTrainer] Training...")
    history = model.fit(
        X, y,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=validation_split,
        callbacks=callbacks,
        shuffle=True,
        verbose=2,
    )

    # Print results
    best_val_loss = min(history.history.get("val_loss", [999]))
    best_val_acc = max(history.history.get("val_accuracy", [0]))
    best_train_acc = max(history.history.get("accuracy", [0]))

    print(f"\n[ModelTrainer] ---- Results ----")
    print(f"  Best training accuracy:   {best_train_acc:.4f}")
    print(f"  Best validation accuracy: {best_val_acc:.4f}")
    print(f"  Best validation loss:     {best_val_loss:.4f}")

    if best_val_acc < 0.85:
        print(
            "\n[ModelTrainer] WARNING: Validation accuracy is below 85%. "
            "Consider:\n"
            "  - Recording more distinct gestures\n"
            "  - Ensuring consistent hand position during recording\n"
            "  - Checking if two gestures look too similar"
        )

    _ensure_parent_dir(model_output_path)
    model.save(model_output_path)
    print(f"\n[ModelTrainer] Model saved to {model_output_path}")
    print(f"[ModelTrainer] Label map saved to {label_map_path}")
    print(f"[ModelTrainer] Feature stats saved to {feature_stats_path}")

    return model


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Train gesture ANN model. Base gestures: "
        + ", ".join(BASE_GESTURES)
    )
    parser.add_argument("--csv", default="data")
    parser.add_argument("--model", default="models/gesture_ann.keras")
    parser.add_argument("--label-map", default="models/label_map.json")
    parser.add_argument("--feature-stats", default=FEATURE_STATS_DEFAULT_PATH)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--val-split", type=float, default=0.2)

    args = parser.parse_args()

    train_model(
        csv_path=args.csv,
        model_output_path=args.model,
        label_map_path=args.label_map,
        feature_stats_path=args.feature_stats,
        epochs=args.epochs,
        batch_size=args.batch_size,
        validation_split=args.val_split,
    )
