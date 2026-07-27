import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

with driver.session() as session:
    print("=" * 50)
    print("STUDIED ILISKILERI")
    print("=" * 50)
    r1 = session.run("MATCH ()-[r:STUDIED]->() RETURN count(r) AS total")
    for rec in r1:
        print(f"Toplam STUDIED iliskisi: {rec['total']}")

    print()
    print("SON 10 STUDIED KAYDI")
    print("=" * 50)
    r2 = session.run("""
        MATCH (u:User)-[r:STUDIED]->(c:Concept)
        RETURN u.id AS user_id, c.name AS concept, r.attempts AS attempts,
               r.last_score AS last_score, r.last_studied AS last_studied
        ORDER BY r.last_studied DESC
        LIMIT 10
    """)
    for rec in r2:
        print(f"  {rec['user_id']} -> {rec['concept']} | deneme: {rec['attempts']} | "
              f"son skor: {rec['last_score']} | son tarih: {rec['last_studied']}")

driver.close()
print()
print("Kontrol tamamlandi!")
