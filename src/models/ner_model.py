"""
ner_model.py

Domain-specific Named Entity Recognition for aerospace failure reports.

Approach: spaCy's statistical NER (general entities — ORG, DATE, GPE, etc.)
combined with a rule-based EntityRuler seeded with a curated aerospace-failure
vocabulary, for four domain labels:
    SUBSYSTEM            - the hardware/software system involved
    MISSION_PHASE         - when in the mission timeline the failure occurred
    FAILURE_TYPE           - the technical failure mechanism
    ROOT_CAUSE_CATEGORY   - a coarse causal bucket (for cross-mission grouping)

This differs from the old graph_builder.py regex approach in an important way:
patterns here match individual entity SPANS and only label the words actually
present in the text. They never assert an entire pre-written record (mission +
cause) off one keyword hit, and they aren't tied to any specific mission —
the vocabulary is generic engineering terminology, so this generalizes to
any new report you add to the corpus, not just the five you started with.

Install: pip install spacy && python -m spacy download en_core_web_sm
(en_core_web_sm is CPU-friendly; swap to en_core_web_trf for higher accuracy
if you have the compute budget.)
"""

import spacy
from spacy.pipeline import EntityRuler
from collections import Counter

MODEL_NAME = "en_core_web_sm"

# Domain vocabulary — generic engineering terms, not mission-specific facts.
# Extend these lists as you read more reports; that's the intended workflow,
# unlike the old approach where adding a mission meant adding a fixed answer.
SUBSYSTEM_TERMS = [
    "solid rocket booster", "thermal protection system", "guidance navigation and control",
    "propulsion system", "inertial reference system", "avionics", "power system",
    "communication system", "parachute system", "flight software", "attitude control system",
    "reaction control system", "landing gear", "heat shield", "radar altimeter",
    "backshell", "descent engine", "onboard computer", "sensor suite", "battery system",
    "solar array", "thruster", "navigation software",
]

MISSION_PHASE_TERMS = [
    "ascent", "descent", "launch", "reentry", "re-entry", "orbital insertion",
    "powered descent", "cruise phase", "landing phase", "separation", "braking phase",
    "rough braking", "fine braking", "terminal descent", "atmospheric entry",
    "lunar bound maneuver", "trajectory correction maneuver", "coast phase", "touchdown",
]

FAILURE_TYPE_TERMS = [
    "seal erosion", "software exception", "structural failure", "sensor malfunction",
    "loss of communication", "thruster failure", "trajectory deviation", "overheating",
    "debris impact", "unit conversion error", "integer overflow", "premature shutdown",
    "false signal", "power depletion", "structural breach", "guidance error",
    "burn-through", "signal loss", "hardware fault", "timing error",
]

# Coarse causal taxonomy — deliberately generic so two failures from different
# missions can land in the same bucket even when their literal wording differs.
# This is what makes a cross-mission "shared root cause" comparison possible
# alongside the BERT embedding similarity in embeddings.py.
ROOT_CAUSE_CATEGORIES = {
    "design_error": ["design flaw", "design deficiency", "inadequate design", "design margin"],
    "software_defect": ["software bug", "software error", "coding error", "software exception",
                         "algorithm error", "software glitch"],
    "material_failure": ["material fatigue", "material failure", "corrosion", "erosion",
                          "structural fatigue", "seal degradation"],
    "process_human_error": ["procedural error", "human error", "inadequate testing",
                             "insufficient validation", "process failure", "oversight"],
    "environmental_factor": ["low temperature", "cold weather", "extreme temperature",
                              "weather condition", "environmental condition"],
    "communication_gap": ["miscommunication", "specification error", "requirements gap",
                           "unit mismatch", "interface mismatch", "documentation error"],
}


class FailureNER:
    def __init__(self, model_name: str = MODEL_NAME):
        print(f"Loading spaCy model: {model_name}...")
        self.nlp = spacy.load(model_name)
        self._add_domain_ruler()

    def _add_domain_ruler(self):
        ruler = self.nlp.add_pipe("entity_ruler", before="ner")
        patterns = []
        for term in SUBSYSTEM_TERMS:
            patterns.append({"label": "SUBSYSTEM", "pattern": term})
        for term in MISSION_PHASE_TERMS:
            patterns.append({"label": "MISSION_PHASE", "pattern": term})
        for term in FAILURE_TYPE_TERMS:
            patterns.append({"label": "FAILURE_TYPE", "pattern": term})
        ruler.add_patterns(patterns)

    def extract_entities(self, text: str) -> dict:
        """Returns every matched span per domain label, plus spaCy's general entities."""
        doc = self.nlp(text)
        result = {
            "subsystem": [], "mission_phase": [], "failure_type": [],
            "general_entities": [],
        }
        for ent in doc.ents:
            if ent.label_ == "SUBSYSTEM":
                result["subsystem"].append(ent.text)
            elif ent.label_ == "MISSION_PHASE":
                result["mission_phase"].append(ent.text)
            elif ent.label_ == "FAILURE_TYPE":
                result["failure_type"].append(ent.text)
            else:
                result["general_entities"].append((ent.text, ent.label_))
        return result

    def categorize_root_cause(self, text: str) -> str | None:
        """Assigns one coarse root-cause category by keyword presence, or None if no match."""
        text_lower = text.lower()
        for category, keywords in ROOT_CAUSE_CATEGORIES.items():
            if any(kw in text_lower for kw in keywords):
                return category
        return None

    def extract_structured_fields(self, text: str) -> dict:
        """
        Reduces raw entity spans to a best-guess single value per field, in the
        same shape graph_builder.py's extraction step expects — so this can be
        swapped in as the primary extractor.
        Uses most-frequent span per label; returns None for a field with no hits.
        """
        raw = self.extract_entities(text)

        def most_common(spans: list[str]) -> str | None:
            if not spans:
                return None
            return Counter(spans).most_common(1)[0][0]

        return {
            "subsystem": most_common(raw["subsystem"]),
            "mission_phase": most_common(raw["mission_phase"]),
            "failure_type": most_common(raw["failure_type"]),
            "root_cause_category": self.categorize_root_cause(text),
            "has_entities": bool(raw["subsystem"] or raw["failure_type"]),
        }


if __name__ == "__main__":
    ner = FailureNER()
    test_text = ("The O-ring primary seal exhibited erosion during the ascent phase, "
                 "attributed to the low ambient temperature affecting the solid rocket booster's joint resiliency.")
    print(ner.extract_structured_fields(test_text))