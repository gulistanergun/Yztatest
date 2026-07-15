"""LearnSphere için basit bir yarı ömür (half-life) tabanlı unutma baseline modeli eğitir.

Model bilerek hafif tasarlanmıştır (MVP/Baseline):
- numpy/pandas dışında harici bir makine öğrenmesi (ML) kütüphanesi bağımlılığı yoktur.
- Hatırlama olasılığını p = 2 ** (-elapsed_days / half_life) formülüyle tahmin eder.
- Yarı ömrü (half-life) exp(doğrusal_özellikler) olarak öğrenir.

Bu nihai üretim modeli değildir. Veri bilimi adımlarını kanıtlayan ve
proje incelemesi için metrikler üreten tekrarlanabilir bir baseline modeldir.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# Modele girdi olarak verilecek temel özellik kolonları
FEATURE_COLUMNS = [
    "difficulty",
    "prior_exposures",
    "successful_recalls",
    "failed_recalls",
    "prior_accuracy",
    "motivation",
    "prior_knowledge",
]


def make_features(df: pd.DataFrame, stats: dict | None = None) -> tuple[np.ndarray, dict]:
    """Özellik mühendisliği ve ölçeklendirme (normalization) işlemlerini yapar."""
    features = df[FEATURE_COLUMNS].copy()
    
    # Dağılımı düzeltmek için sıklık verilerine log(1+x) dönüşümü uygulanır
    features["prior_exposures"] = np.log1p(features["prior_exposures"])
    features["successful_recalls"] = np.log1p(features["successful_recalls"])
    features["failed_recalls"] = np.log1p(features["failed_recalls"])

    # Eğer geçmiş istatistikler yoksa (eğitim aşaması), ortalama ve standart sapma hesaplanır
    if stats is None:
        means = features.mean()
        stds = features.std().replace(0, 1)
        stats = {
            "means": means.to_dict(),
            "stds": stds.to_dict(),
        }
    else:
        # Test veya tahmin aşamasında eğitim istatistikleri kullanılır
        means = pd.Series(stats["means"])
        stds = pd.Series(stats["stds"])

    # Özellikler standartlaştırılır (Z-score normalizasyonu)
    scaled = (features - means) / stds
    
    # Matris çarpımı için sabit terim (bias/intercept) sütunu eklenir (hep 1 olan sütun)
    intercept = np.ones((len(scaled), 1))
    return np.hstack([intercept, scaled.to_numpy(dtype=float)]), stats


def predict_hlr_probability(x: np.ndarray, elapsed_days: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """HLR formülüne göre hatırlama olasılığını ve tahmini yarı ömrü (half-life) hesaplar."""
    # Özellikler ile ağırlıkların matris çarpımı yapılır (z = x * w)
    z = x @ weights
    
    # Hafıza yarı ömrü (half-life) üstel fonksiyonla elde edilir, uç değerler kırpılır
    half_life = np.exp(np.clip(z, -2.5, 4.5))
    
    # Hatırlama olasılığı p = 2 ** (-elapsed_days / half_life)
    probability = 2 ** (-elapsed_days / np.maximum(half_life, 0.15))
    
    # Sayısal kararlılık için olasılık değerleri [1e-5, 1 - 1e-5] aralığına kırpılır
    return np.clip(probability, 1e-5, 1 - 1e-5), half_life


def binary_log_loss(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """İki sınıflı sınıflandırma için logaritmik kaybı (Binary Cross-Entropy Loss) hesaplar."""
    y_prob = np.clip(y_prob, 1e-5, 1 - 1e-5)
    return float(-np.mean(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob)))


def accuracy(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5) -> float:
    """Tahmin olasılıklarının belirlenen eşiğe göre doğruluk oranını hesaplar."""
    return float(np.mean((y_prob >= threshold) == y_true))


def roc_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Modelin ayırt edici gücünü ölçmek için ROC-AUC skorunu hesaplar."""
    positives = y_prob[y_true == 1]
    negatives = y_prob[y_true == 0]
    if len(positives) == 0 or len(negatives) == 0:
        return float("nan")
    comparisons = (positives[:, None] > negatives[None, :]).mean()
    ties = 0.5 * (positives[:, None] == negatives[None, :]).mean()
    return float(comparisons + ties)


def rule_based_probability(df: pd.DataFrame) -> np.ndarray:
    """Kural tabanlı (rule-based) baseline için hatırlama olasılığını hesaplar.
    
    Bu fonksiyon, makine öğrenmesi yerine el yordamıyla belirlenmiş sabit kural ve katsayıları kullanır.
    """
    half_life = (
        0.9
        + 0.45 * np.log1p(df["prior_exposures"].to_numpy())
        + 1.25 * df["prior_accuracy"].to_numpy()
        + 0.75 * df["prior_knowledge"].to_numpy()
        + 0.30 * df["motivation"].to_numpy()
        - 0.65 * df["difficulty"].to_numpy()
    )
    half_life = np.maximum(0.35, half_life)
    prob = 2 ** (-df["elapsed_days"].to_numpy() / half_life)
    return np.clip(prob, 1e-5, 1 - 1e-5)


def train_hlr(
    train_df: pd.DataFrame,
    learning_rate: float,
    epochs: int,
    l2: float,
) -> tuple[np.ndarray, dict, list[float]]:
    """Gradyan inişi (Gradient Descent) ile HLR modelinin ağırlıklarını eğitir."""
    # Eğitim verisinden özellikleri hazırlar ve ölçekler
    x_train, stats = make_features(train_df)
    
    # Hedef değişken (gerçek quiz sonucu: 1=doğru, 0=yanlış)
    y = train_df["recall_correct"].to_numpy(dtype=float)
    
    # Son görülmeden beri geçen gün sayısı
    elapsed = train_df["elapsed_days"].to_numpy(dtype=float)

    # Ağırlık matrisi (weights) sıfırlarla başlatılır, sabit terim (bias) ağırlığı 0.8 ile başlar
    weights = np.zeros(x_train.shape[1], dtype=float)
    weights[0] = 0.8
    losses = []
    ln2 = np.log(2.0)

    # Gradyan İnişi Optimizasyon Döngüsü
    for _ in range(epochs):
        # Yarı ömür ve hatırlama olasılığı tahmin edilir
        probability, half_life = predict_hlr_probability(x_train, elapsed, weights)
        
        # BCE log loss hesaplanır ve L2 regülarizasyon cezası eklenir
        loss = binary_log_loss(y, probability) + l2 * float(np.sum(weights[1:] ** 2))
        losses.append(loss)

        # BCE kaybının ağırlıklara göre türevi (gradyan) hesaplanır
        denom = np.maximum(1 - probability, 1e-4)
        d_loss_d_z = (probability - y) * ln2 * elapsed / (half_life * denom)
        gradient = (x_train.T @ d_loss_d_z) / len(x_train)
        
        # Sabit terim hariç diğer ağırlıklar için L2 regülarizasyon gradyanı eklenir
        gradient[1:] += 2 * l2 * weights[1:]
        
        # Ağırlıklar güncellenir
        weights -= learning_rate * gradient

    return weights, stats, losses


def evaluate(name: str, y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    """Modelin metriklerini derleyen yardımcı fonksiyon."""
    return {
        "model": name,
        "rows": int(len(y_true)),
        "accuracy": round(accuracy(y_true, y_prob), 4),
        "log_loss": round(binary_log_loss(y_true, y_prob), 4),
        "roc_auc": round(roc_auc(y_true, y_prob), 4),
        "mean_predicted_recall": round(float(np.mean(y_prob)), 4),
    }


def make_recommendations(
    logs: pd.DataFrame,
    concepts: pd.DataFrame,
    users: pd.DataFrame,
    weights: np.ndarray,
    stats: dict,
    output_path: Path,
    current_day: int,
) -> None:
    """Quiz ajanı için unutulma riski en yüksek ilk 50 kullanıcı-konu eşleşmesini hazırlar."""
    # Sadece sınav (quiz) hareketlerini filtrele
    quiz_logs = logs[logs["event_type"] == "quiz"].copy()
    if quiz_logs.empty:
        output_path.write_text("", encoding="utf-8")
        return

    # Her kullanıcının her konu için katıldığı en son quizi al
    grouped = quiz_logs.sort_values("day_index").groupby(["user_id", "concept_id"], as_index=False).tail(1)
    
    # Kullanıcı-konu bazlı geçmiş performans istatistiklerini hesapla
    history = quiz_logs.groupby(["user_id", "concept_id"]).agg(
        successful_recalls=("recall_correct", "sum"),
        failed_recalls=("recall_correct", lambda values: int((values == 0).sum())),
        prior_accuracy=("recall_correct", "mean"),
        prior_exposures=("recall_correct", "count"),
    )
    
    # Verileri birleştir (kullanıcı profilleri ve konu zorlukları ile)
    candidates = grouped.merge(history, on=["user_id", "concept_id"], suffixes=("", "_history"))
    candidates = candidates.merge(users, on="user_id", how="left")
    candidates = candidates.merge(concepts, on="concept_id", how="left", suffixes=("", "_concept"))
    
    # Son quiz gününden bu yana geçen gün sayısını hesapla
    candidates["elapsed_days"] = current_day - candidates["day_index"]
    candidates["difficulty"] = candidates["difficulty_concept"].fillna(candidates["difficulty"])

    # Özellikleri hazırla ve model tahminini üret
    x_candidates, _ = make_features(candidates, stats)
    probability, half_life = predict_hlr_probability(
        x_candidates,
        candidates["elapsed_days"].to_numpy(dtype=float),
        weights,
    )
    
    # Risk skorunu hesapla (Risk Skoru = 1 - Hatırlama İhtimali)
    candidates["predicted_recall_probability"] = probability
    candidates["estimated_half_life_days"] = half_life
    candidates["risk_score"] = 1 - candidates["predicted_recall_probability"]
    
    # En yüksek riske sahip olanları en üstte olacak şekilde sırala
    candidates = candidates.sort_values("risk_score", ascending=False)

    columns = [
        "user_id",
        "concept_id",
        "concept_name",
        "category",
        "elapsed_days",
        "prior_exposures",
        "prior_accuracy",
        "predicted_recall_probability",
        "estimated_half_life_days",
        "risk_score",
    ]
    # En riskli ilk 50 kaydı CSV olarak kaydet
    candidates[columns].head(50).to_csv(output_path, index=False)


def save_feature_weights(path: Path, weights: np.ndarray) -> None:
    """Modelin öğrendiği ağırlık katsayılarını CSV dosyası olarak kaydeder."""
    rows = [{"feature": "intercept", "weight": weights[0]}]
    rows.extend({"feature": name, "weight": weight} for name, weight in zip(FEATURE_COLUMNS, weights[1:]))
    pd.DataFrame(rows).to_csv(path, index=False)


def parse_args() -> argparse.Namespace:
    """Komut satırı argümanlarını ayrıştırır."""
    parser = argparse.ArgumentParser(description="LearnSphere baseline unutma modelini eğitir.")
    parser.add_argument("--data-dir", default="data-science/data", type=Path)
    parser.add_argument("--output-dir", default="data-science/outputs", type=Path)
    parser.add_argument("--epochs", default=800, type=int)
    parser.add_argument("--learning-rate", default=0.045, type=float)
    parser.add_argument("--l2", default=0.001, type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Modelleme veri setinin varlığını kontrol et
    dataset_path = args.data_dir / "modeling_dataset.csv"
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"{dataset_path} bulunamadı. Eğitime başlamadan önce generate_synthetic_data.py dosyasını çalıştırın."
        )

    # Veriyi yükle ve gün sırasına göre sırala
    dataset = pd.read_csv(dataset_path).sort_values(["day_index", "user_id", "concept_id"]).reset_index(drop=True)
    
    # Veriyi kronolojik olarak %80 eğitim ve %20 test olarak böl (Train-Test Split)
    split_index = int(len(dataset) * 0.8)
    train_df = dataset.iloc[:split_index].copy()
    test_df = dataset.iloc[split_index:].copy()

    # HLR Modelini eğit
    weights, stats, losses = train_hlr(train_df, args.learning_rate, args.epochs, args.l2)

    # Test verisi üzerinde tahminler yap
    x_test, _ = make_features(test_df, stats)
    y_test = test_df["recall_correct"].to_numpy(dtype=float)
    elapsed_test = test_df["elapsed_days"].to_numpy(dtype=float)
    hlr_prob, _ = predict_hlr_probability(x_test, elapsed_test, weights)
    
    # Karşılaştırma için kural tabanlı olasılıkları hesapla
    rule_prob = rule_based_probability(test_df)

    # Sonuç metriklerini oluştur
    metrics = {
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "features": FEATURE_COLUMNS,
        "rule_based_baseline": evaluate("rule_based_baseline", y_test, rule_prob),
        "hlr_inspired_model": evaluate("hlr_inspired_model", y_test, hlr_prob),
        "final_training_loss": round(float(losses[-1]), 4),
        "loss_first_epoch": round(float(losses[0]), 4),
    }

    # Metrikleri kaydet
    (args.output_dir / "model_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # Ağırlıkları kaydet
    save_feature_weights(args.output_dir / "feature_weights.csv", weights)

    # En riskli konu önerilerini oluştur
    logs = pd.read_csv(args.data_dir / "synthetic_learning_logs.csv")
    concepts = pd.read_csv(args.data_dir / "concepts.csv")
    users = pd.read_csv(args.data_dir / "users.csv")
    current_day = int(logs["day_index"].max()) + 1
    make_recommendations(
        logs,
        concepts,
        users,
        weights,
        stats,
        args.output_dir / "at_risk_recommendations.csv",
        current_day,
    )

    # Sonuçları ekrana yazdır
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
