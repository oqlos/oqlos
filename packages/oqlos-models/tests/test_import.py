from oqlos.models.dsl_models import CqlDocument, CqlGoal
from oqlos.models.scenario import Goal, Scenario, Step


def test_models_importable():
    assert CqlDocument().goals == []
    assert Step(id="s1", action="noop", label=None).id == "s1"
    assert Goal(
        id="g1",
        name="G",
        description="",
        steps=[],
        expectedResult="",
        validationCriteria=[],
    ).id == "g1"
    assert Scenario(
        id="sc1",
        name="S",
        description="",
        device="dev",
        protocol="proto",
        goals=[],
    ).id == "sc1"
