import json
import re
from pathlib import Path
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "password"

# Rule-based engineering ontology patterns for aerospace incident extraction
EXTRACTION_RULES = [
    {
        "pattern": r"(O-ring|seal|joint|cold temperature|blow-by|erosion)",
        "mission": "STS-51-L Challenger",
        "subsystem": "Solid Rocket Booster (SRB)",
        "failure_mode": "O-ring Primary/Secondary Seal Erosion",
        "root_cause": "Low Ambient Launch Temperature and Joint Resiliency Loss"
    },
    {
        "pattern": r"(foam|bipod ramp|tile|left wing|leading edge|RCC panel)",
        "mission": "STS-107 Columbia",
        "subsystem": "Thermal Protection System (TPS)",
        "failure_mode": "Left Wing RCC Panel Breached by Foam Debris",
        "root_cause": "Insulation Foam Shedding During Ascent"
    },
    {
        "pattern": r"(operand error|integer overflow|horizontal bias|alignment|SRI|Inertial Reference)",
        "mission": "Ariane 5 Flight 501",
        "subsystem": "Inertial Reference System (SRI)",
        "failure_mode": "Software Arithmetic Exception / 64-bit to 16-bit Overflow",
        "root_cause": "Software Reuse without Specification Recalibration"
    },
    {
        "pattern": r"(metric|english units|newton|pound-seconds|thruster firing|trajectory correction)",
        "mission": "Mars Climate Orbiter",
        "subsystem": "Angular Momentum Desaturation (AMD) Software",
        "failure_mode": "Trajectory Navigation Discrepancy",
        "root_cause": "Unit Mismatch (Metric vs English Units)"
    },
    {
        "pattern": r"(IMU|saturation|radar altimeter|backshell|parachute|Schiaparelli)",
        "mission": "ExoMars 2016 Schiaparelli",
        "subsystem": "Guidance, Navigation and Control (GNC)",
        "failure_mode": "Premature Parachute Jettison and Thruster Cutoff",
        "root_cause": "IMU Saturation Induced False Negative Altitude Calculation"
    }
]

def build_knowledge_graph():
    """Extracts entities from chunked text and creates causal graph relationships."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    chunks_dir = base_dir / "data" / "processed" / "chunks"
    
    json_files = list(chunks_dir.glob("*_chunks.json"))
    if not json_files:
        print(f"No chunk files found in {chunks_dir}.")
        return

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    print(f"Connected to Neo4j. Building FMEA causal graph...\n{'='*60}")

    total_relations_created = 0

    with driver.session() as session:
        for json_path in json_files:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for chunk in data["chunks"]:
                text = chunk["text"]
                chunk_id = chunk["chunk_id"]

                for rule in EXTRACTION_RULES:
                    if re.search(rule["pattern"], text, re.IGNORECASE):
                        session.run("""
                            MATCH (c:Chunk {id: $chunk_id})
                            MERGE (m:Mission {name: $mission})
                            MERGE (s:Subsystem {name: $subsystem})
                            MERGE (fm:FailureMode {name: $failure_mode})
                            MERGE (rc:RootCause {description: $root_cause})

                            MERGE (c)-[:MENTIONS]->(fm)
                            MERGE (m)-[:EXPERIENCED_FAILURE]->(fm)
                            MERGE (fm)-[:OCCURRED_IN_SUBSYSTEM]->(s)
                            MERGE (fm)-[:CAUSED_BY]->(rc)
                        """, {
                            "chunk_id": chunk_id,
                            "mission": rule["mission"],
                            "subsystem": rule["subsystem"],
                            "failure_mode": rule["failure_mode"],
                            "root_cause": rule["root_cause"]
                        })
                        total_relations_created += 1

    driver.close()
    print(f"{'='*60}\nKnowledge Graph Built: Established {total_relations_created} causal links and entity nodes.")

if __name__ == "__main__":
    build_knowledge_graph()