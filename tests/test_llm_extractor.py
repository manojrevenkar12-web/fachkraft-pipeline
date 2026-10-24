"""The model extractor is held to evidence: quotes must exist, values must be in the vocabulary,
and it only fills what the rules left empty."""

from datetime import date
from types import SimpleNamespace

from fkp.extract.llm import ClaudeExtractor, HybridExtractor, validate

TODAY = date(2026, 10, 26)


class Stub:
    def __init__(self, facts=None, fail=False):
        self.facts, self.fail, self.calls = facts or [], fail, []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("overloaded")
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"facts": self.facts})])


def test_validation_rejects_invented_quotes_and_values():
    text = "Ich mache seit Jahren Elektroinstallationen auf Baustellen"
    assert validate({"field": "occupation", "value": ["elektroniker"], "quote": "Elektroinstallationen"}, text, TODAY)
    assert validate({"field": "occupation", "value": ["elektroniker"], "quote": "Elektriker"}, text, TODAY) is None  # not in the message
    assert validate({"field": "occupation", "value": ["astronaut"], "quote": "Baustellen"}, text, TODAY) is None
    assert validate({"field": "start_date", "value": "2020-01-01", "quote": "seit"}, text, TODAY) is None  # in the past
    assert validate({"field": "german_level", "value": "native", "quote": "seit"}, text, TODAY) is None


def test_hybrid_fills_only_gaps_and_survives_model_errors():
    text = "Ich mache seit 6 Jahren Elektroinstallationen auf Baustellen in München"
    stub = Stub([{"field": "occupation", "value": ["elektroniker"], "quote": "Elektroinstallationen"},
                 {"field": "experience_years", "value": 99, "quote": "6 Jahren"}])
    h = HybridExtractor(ClaudeExtractor(client=stub))
    r = h.read(text, "de", TODAY)
    v = {f.field: f.value for f in r.facts}
    assert v["occupation"] == ["elektroniker"] and v["experience_years"] == 6 and v["location"]["place"] == "München"
    assert "Elektroinstallationen" in r.get("occupation").evidence(text)
    assert "{" not in stub.calls[0]["system"] and "Mehmet" not in str(stub.calls[0])
    r2 = HybridExtractor(ClaudeExtractor(client=Stub(fail=True))).read(text, "de", TODAY)
    assert {f.field for f in r2.facts} == {"location", "experience_years"}


def test_opt_out_never_reaches_the_model():
    stub = Stub()
    HybridExtractor(ClaudeExtractor(client=stub)).read("STOP", "de", TODAY)
    assert stub.calls == []
