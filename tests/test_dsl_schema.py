from oqlos.dsl import get_default_dsl_schema


def test_default_schema_exposes_only_the_oql_dialect():
    schema = get_default_dsl_schema()

    dialect_ids = {dialect.id for dialect in schema.dialects}

    assert dialect_ids == {"oql"}
    assert all(item.dialects == ["oql"] for item in schema.objects)
    assert all(item.dialects == ["oql"] for item in schema.functions)
    assert schema.objects
    assert schema.functions


def test_explicit_object_and_param_maps_override_inferred_fallbacks():
    schema = get_default_dsl_schema()

    assert schema.objectFunctionMap["pompa"].functions == ["SET", "WAIT", "SAVE"]
    assert schema.paramUnitMap["ciśnienie"].units == ["mbar", "bar"]
    assert "ASSERT_STATUS" in schema.objectFunctionMap["api"].functions
    assert schema.paramUnitMap["czas"].units == ["ms", "s", "min"]
