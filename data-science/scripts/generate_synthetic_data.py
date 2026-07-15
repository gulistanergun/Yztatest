"""Sentetik LearnSphere öğrenme ve quiz geçmişi üretir.

Bu script, veri bilimi ekibi için bir yapay (mock) veri seti hazırlar:
- 100 yapay öğrenci
- 30 günlük çalışma/quiz logları
- Konsept düzeyinde zorluk dereceleri
- Ebbinghaus unutma eğrisi tarzında bir azalma modelini izleyen hatırlama etiketleri

Ekibin çalışmayı tekrarlayabilmesi için çıktı varsayılan olarak sabittir (deterministik).
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

# Sistemde kullanılan konular, kategorileri ve statik zorluk dereceleri (0.0 - 1.0 arası)
CONCEPTS = [
    ("python-basics", "Python Basics", "programming", 0.22),
    ("oop", "Object-Oriented Programming", "programming", 0.48),
    ("sql-joins", "SQL Joins", "data", 0.42),
    ("pandas", "Pandas DataFrames", "data", 0.38),
    ("statistics", "Statistics Fundamentals", "data-science", 0.55),
    ("linear-regression", "Linear Regression", "machine-learning", 0.50),
    ("classification", "Classification Metrics", "machine-learning", 0.52),
    ("rag", "Retrieval-Augmented Generation", "ai", 0.62),
    ("prompt-engineering", "Prompt Engineering", "ai", 0.35),
    ("vector-db", "Vector Databases", "ai", 0.58),
    ("neo4j-graph", "Neo4j Knowledge Graphs", "backend", 0.57),
    ("fastapi", "FastAPI Backend", "backend", 0.40),
]


@dataclass
class MemoryState:
    """Kullanıcının belirli bir konudaki hafıza durumunu takip eder."""
    exposures: int = 0  # Konuyu toplamda kaç kez gördüğü (çalışma + quiz)
    successful_recalls: int = 0  # Quizlerdeki başarılı hatırlama sayısı
    failed_recalls: int = 0  # Quizlerdeki başarısız hatırlama sayısı
    last_seen_day: int | None = None  # Konunun son görüldüğü gün indeksi
    stability: float = 1.4  # Hafıza kararlılık/kalıcılık katsayısı


def recall_probability(elapsed_days: int, stability: float, difficulty: float) -> float:
    """Ebbinghaus benzeri hatırlama olasılığı hesabı: Süre geçtikçe hatırlama olasılığı düşer."""
    # Yarı ömür = kararlılık * (1.15 - zorluk)
    half_life = max(0.4, stability * (1.15 - difficulty))
    return 2 ** (-elapsed_days / half_life)


def update_memory_after_study(state: MemoryState, current_day: int, study_minutes: int) -> None:
    """Kullanıcı bir konuyu çalıştığında hafıza durumunu (stability) günceller."""
    state.exposures += 1
    state.last_seen_day = current_day
    # Çalışma süresine bağlı olarak hafıza kararlılığı artırılır
    state.stability += 0.30 + min(study_minutes, 60) / 160


def update_memory_after_quiz(state: MemoryState, current_day: int, correct: int) -> None:
    """Kullanıcı bir quiz çözdüğünde quiz sonucuna göre hafıza durumunu günceller."""
    state.exposures += 1
    state.last_seen_day = current_day
    if correct:
        state.successful_recalls += 1
        state.stability += 0.65  # Başarılı cevap kararlılığı artırır
    else:
        state.failed_recalls += 1
        # Başarısız cevap hafıza kararlılığını düşürür
        state.stability = max(0.7, state.stability * 0.88)


def make_event_id(user_id: str, day_index: int, event_index: int) -> str:
    """Tekil bir olay ID'si (event_id) üretir."""
    return f"{user_id}-d{day_index:02d}-e{event_index:03d}"


def generate_dataset(
    output_dir: Path,
    users: int,
    days: int,
    seed: int,
    start_date: date,
) -> None:
    """Belirtilen gün ve kullanıcı sayısı için yapay veri seti üretir ve kaydeder."""
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Konuları ID'lerine göre haritalandır
    concepts_by_id = {concept_id: (name, category, difficulty) for concept_id, name, category, difficulty in CONCEPTS}
    user_profiles = []
    logs = []
    modeling_rows = []
    state_by_user_concept: dict[tuple[str, str], MemoryState] = defaultdict(MemoryState)

    # 1. Kullanıcı Profillerinin Oluşturulması
    for user_index in range(1, users + 1):
        user_id = f"user_{user_index:03d}"
        motivation = rng.uniform(0.55, 1.20)
        prior_knowledge = rng.uniform(0.15, 0.85)
        user_profiles.append(
            {
                "user_id": user_id,
                "motivation": round(motivation, 3),
                "prior_knowledge": round(prior_knowledge, 3),
            }
        )

        # Her kullanıcının ilgilendiği 4 ila 7 adet öncelikli konu seçilir
        preferred_concepts = rng.sample([item[0] for item in CONCEPTS], k=rng.randint(4, 7))
        event_index = 0

        # 2. 30 Günlük Zaman Akışı
        for day_index in range(days):
            current_date = start_date + timedelta(days=day_index)
            # Bir günde yapılabilecek olay sayısı olasılık dağılımı
            daily_events = rng.choices([0, 1, 2, 3], weights=[0.12, 0.34, 0.34, 0.20], k=1)[0]

            for _ in range(daily_events):
                event_index += 1
                # Konu seçimi (%75 olasılıkla ilgi alanı, %25 diğer konular)
                concept_id = rng.choice(preferred_concepts if rng.random() < 0.75 else list(concepts_by_id))
                concept_name, category, difficulty = concepts_by_id[concept_id]
                state = state_by_user_concept[(user_id, concept_id)]
                
                # Etkinlik türü (ilk kez görüyorsa zorunlu "study", aksi halde olasılığa göre study veya quiz)
                event_type = "study" if state.exposures == 0 or rng.random() < 0.62 else "quiz"
                elapsed_days = 0 if state.last_seen_day is None else day_index - state.last_seen_day
                prior_accuracy = (
                    state.successful_recalls / max(1, state.successful_recalls + state.failed_recalls)
                )

                # Çalışma (Study) Etkinliği
                if event_type == "study":
                    study_minutes = rng.randint(8, 45)
                    update_memory_after_study(state, day_index, study_minutes)
                    logs.append(
                        {
                            "event_id": make_event_id(user_id, day_index, event_index),
                            "user_id": user_id,
                            "event_date": current_date.isoformat(),
                            "day_index": day_index,
                            "event_type": event_type,
                            "concept_id": concept_id,
                            "concept_name": concept_name,
                            "category": category,
                            "difficulty": round(difficulty, 3),
                            "elapsed_days": elapsed_days,
                            "prior_exposures": state.exposures - 1,
                            "prior_accuracy": round(prior_accuracy, 3),
                            "study_minutes": study_minutes,
                            "quiz_score": "",
                            "recall_correct": "",
                        }
                    )
                    continue

                # Sınav (Quiz) Etkinliği
                base_probability = recall_probability(elapsed_days, state.stability, difficulty)
                # Ön bilgi ve motivasyon eklenerek nihai hatırlama olasılığı belirlenir
                probability = min(
                    0.97,
                    max(0.03, base_probability + 0.10 * prior_knowledge + 0.07 * (motivation - 0.8)),
                )
                correct = 1 if rng.random() < probability else 0
                # Doğru/yanlış durumuna göre rastgele quiz skoru üretilir
                quiz_score = rng.randint(75, 100) if correct else rng.randint(20, 70)

                # Modelleme verisine ekle (sadece quiz durumları modele beslenir)
                modeling_rows.append(
                    {
                        "user_id": user_id,
                        "concept_id": concept_id,
                        "event_date": current_date.isoformat(),
                        "day_index": day_index,
                        "difficulty": round(difficulty, 3),
                        "elapsed_days": elapsed_days,
                        "prior_exposures": state.exposures,
                        "successful_recalls": state.successful_recalls,
                        "failed_recalls": state.failed_recalls,
                        "prior_accuracy": round(prior_accuracy, 3),
                        "motivation": round(motivation, 3),
                        "prior_knowledge": round(prior_knowledge, 3),
                        "quiz_score": quiz_score,
                        "recall_correct": correct,
                        "true_recall_probability": round(probability, 4),
                    }
                )

                update_memory_after_quiz(state, day_index, correct)
                # Genel aktivite loguna ekle
                logs.append(
                    {
                        "event_id": make_event_id(user_id, day_index, event_index),
                        "user_id": user_id,
                        "event_date": current_date.isoformat(),
                        "day_index": day_index,
                        "event_type": event_type,
                        "concept_id": concept_id,
                        "concept_name": concept_name,
                        "category": category,
                        "difficulty": round(difficulty, 3),
                        "elapsed_days": elapsed_days,
                        "prior_exposures": state.exposures - 1,
                        "prior_accuracy": round(prior_accuracy, 3),
                        "study_minutes": "",
                        "quiz_score": quiz_score,
                        "recall_correct": correct,
                    }
                )

    # 3. CSV Dosyalarının Yazılması
    write_csv(output_dir / "users.csv", user_profiles)
    write_csv(
        output_dir / "concepts.csv",
        [
            {
                "concept_id": concept_id,
                "concept_name": concept_name,
                "category": category,
                "difficulty": difficulty,
            }
            for concept_id, concept_name, category, difficulty in CONCEPTS
        ],
    )
    write_csv(output_dir / "synthetic_learning_logs.csv", logs)
    write_csv(output_dir / "modeling_dataset.csv", modeling_rows)

    # Özet istatistik dosyası
    summary = {
        "users": users,
        "days": days,
        "events": len(logs),
        "quiz_rows_for_modeling": len(modeling_rows),
        "average_quiz_success_rate": round(
            sum(row["recall_correct"] for row in modeling_rows) / max(1, len(modeling_rows)),
            4,
        ),
        "seed": seed,
    }
    write_key_value_file(output_dir / "dataset_summary.txt", summary)


def write_csv(path: Path, rows: list[dict]) -> None:
    """Verilen sözlük listesini CSV dosyası olarak yazar."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_key_value_file(path: Path, values: dict) -> None:
    """Anahtar-değer çiftlerini düz metin dosyasına satır satır yazar."""
    lines = [f"{key}: {value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Komut satırı parametrelerini ayrıştırır."""
    parser = argparse.ArgumentParser(description="LearnSphere sentetik veri üretecidir.")
    parser.add_argument("--output-dir", default="data-science/data", type=Path)
    parser.add_argument("--users", default=100, type=int)
    parser.add_argument("--days", default=30, type=int)
    parser.add_argument("--seed", default=42, type=int)
    parser.add_argument("--start-date", default="2026-06-01")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_date = date.fromisoformat(args.start_date)
    generate_dataset(args.output_dir, args.users, args.days, args.seed, start_date)
    print(f"Sentetik veriler başarıyla şu klasöre yazıldı: {args.output_dir}")


if __name__ == "__main__":
    main()
