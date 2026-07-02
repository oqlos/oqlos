"""Canonical shared DSL schema for CQL/OQL editor clients."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DslDialect(BaseModel):
    """Supported DSL dialect metadata."""

    id: str
    name: str
    description: str = ""


class DslItem(BaseModel):
    """A reusable schema item visible to editor clients."""

    id: str
    name: str
    dialects: list[str] = Field(default_factory=list)
    category: str = "general"
    description: str = ""
    type: str | None = None
    symbol: str | None = None
    functions: list[str] = Field(default_factory=list)
    units: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DslFunctionBinding(BaseModel):
    """Object to function relationship used by visual builders."""

    functions: list[str] = Field(default_factory=list)


class DslParamUnitBinding(BaseModel):
    """Param to unit relationship used by visual builders."""

    units: list[str] = Field(default_factory=list)


class DslSchema(BaseModel):
    """Complete editor schema shared by GUI and runtime tooling."""

    source: str = "oqlos"
    dialects: list[DslDialect] = Field(default_factory=list)
    objects: list[DslItem] = Field(default_factory=list)
    functions: list[DslItem] = Field(default_factory=list)
    params: list[DslItem] = Field(default_factory=list)
    units: list[DslItem] = Field(default_factory=list)
    variables: list[DslItem] = Field(default_factory=list)
    objectFunctionMap: dict[str, DslFunctionBinding] = Field(default_factory=dict)
    paramUnitMap: dict[str, DslParamUnitBinding] = Field(default_factory=dict)


def _normalize_name_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _build_inferred_object_function_map(
    objects: list[DslItem],
    functions: list[DslItem],
) -> dict[str, DslFunctionBinding]:
    fallback_names = _normalize_name_list([item.name for item in functions])
    inferred: dict[str, DslFunctionBinding] = {}
    for item in objects:
        inferred[item.name] = DslFunctionBinding(
            functions=_normalize_name_list(item.functions) or fallback_names,
        )
    return inferred


def _build_inferred_param_unit_map(
    params: list[DslItem],
    units: list[DslItem],
) -> dict[str, DslParamUnitBinding]:
    fallback_units = _normalize_name_list(
        [unit.symbol or unit.name for unit in units if (unit.symbol or unit.name)]
    )
    inferred: dict[str, DslParamUnitBinding] = {}
    for item in params:
        inferred[item.name] = DslParamUnitBinding(
            units=_normalize_name_list(item.units) or fallback_units,
        )
    return inferred


def _merge_binding_map(explicit_map, inferred_map, binding_cls, field: str):
    """Overlay explicit bindings (re-normalized) onto an inferred binding map."""
    merged = dict(inferred_map)
    for key, binding in explicit_map.items():
        normalized = _normalize_name_list(getattr(binding, field))
        if normalized:
            merged[key] = binding_cls(**{field: normalized})
    return merged


def _merge_object_function_map(
    explicit_map: dict[str, DslFunctionBinding],
    inferred_map: dict[str, DslFunctionBinding],
) -> dict[str, DslFunctionBinding]:
    return _merge_binding_map(explicit_map, inferred_map, DslFunctionBinding, "functions")


def _merge_param_unit_map(
    explicit_map: dict[str, DslParamUnitBinding],
    inferred_map: dict[str, DslParamUnitBinding],
) -> dict[str, DslParamUnitBinding]:
    return _merge_binding_map(explicit_map, inferred_map, DslParamUnitBinding, "units")


def get_default_dsl_schema() -> DslSchema:
    """Return the canonical cross-project schema used by editor clients."""

    dialects = [
        DslDialect(
            id="cql",
            name="CQL",
            description="Connex Query Language for test scenario authoring in c2004.",
        ),
        DslDialect(
            id="oql",
            name="OQL",
            description="Operation Query Language for OqlOS hardware workflows.",
        ),
    ]

    objects = [
        DslItem(
            id="pump",
            name="pompa",
            dialects=["cql", "oql"],
            category="hardware",
            description="Sterowanie pompą lub regulatorem przepływu.",
            type="actuator",
            functions=["SET", "WAIT", "SAVE", "SAMPLE"],
        ),
        DslItem(
            id="valve",
            name="zawór",
            dialects=["cql", "oql"],
            category="hardware",
            description="Sterowanie zaworami i ich weryfikacja.",
            type="actuator",
            functions=["SET", "WAIT", "ASSERT_VALVE", "SAVE"],
        ),
        DslItem(
            id="sensor",
            name="sensor",
            dialects=["cql", "oql"],
            category="hardware",
            description="Pomiary z czujników ciśnienia, temperatury i wilgotności.",
            type="measurement",
            functions=["VAL", "MIN", "MAX", "SAMPLE", "ASSERT_SENSOR", "FUNC"],
        ),
        DslItem(
            id="api",
            name="api",
            dialects=["oql"],
            category="integration",
            description="Wywołania HTTP i asercje odpowiedzi.",
            type="integration",
            functions=["API_GET", "API_POST", "ASSERT_STATUS", "ASSERT_JSON"],
        ),
        DslItem(
            id="device",
            name="device",
            dialects=["oql"],
            category="diagnostics",
            description="Sprawdzanie sprzętu, magistral i adapterów.",
            type="diagnostic",
            functions=["EXPECT_DEVICE", "EXPECT_I2C_BUS", "EXPECT_I2C_CHIP", "GET_SENSOR"],
        ),
        DslItem(
            id="scenario",
            name="scenario",
            dialects=["cql", "oql"],
            category="control",
            description="Sterowanie przepływem scenariusza i logowanie.",
            type="control",
            functions=["GOTO", "LOG", "WAIT", "ERROR", "INFO"],
        ),
        DslItem(
            id="shell",
            name="shell",
            dialects=["oql"],
            category="integration",
            description="Eksport danych i integracja z shell scripts.",
            type="integration",
            functions=["SHELL_EXPORT", "SAVE_JSON", "LOG"],
        ),
    ]

    functions = [
        DslItem(id="set", name="SET", dialects=["cql", "oql"], category="action", description="Ustaw wartość wyjścia lub zmiennej."),
        DslItem(id="wait", name="WAIT", dialects=["cql", "oql"], category="control", description="Wstrzymaj wykonanie na zadany czas."),
        DslItem(id="val", name="VAL", dialects=["cql", "oql"], category="measurement", description="Odczytaj wartość parametru lub sensora."),
        DslItem(id="save", name="SAVE", dialects=["cql", "oql"], category="data", description="Zapisz wartość do wyniku lub kontekstu."),
        DslItem(id="min", name="MIN", dialects=["cql", "oql"], category="assertion", description="Sprawdź minimalny próg parametru."),
        DslItem(id="max", name="MAX", dialects=["cql", "oql"], category="assertion", description="Sprawdź maksymalny próg parametru."),
        DslItem(id="func", name="FUNC", dialects=["cql", "oql"], category="compute", description="Oblicz wartość pochodną (AVG, SUM, SUB, DIV, MIN)."),
        DslItem(id="sample", name="SAMPLE", dialects=["cql", "oql"], category="measurement", description="Uruchom lub zatrzymaj próbkowanie sygnału."),
        DslItem(id="goto", name="GOTO", dialects=["cql", "oql"], category="control", description="Skocz do innego GOAL lub kroku."),
        DslItem(id="log", name="LOG", dialects=["cql", "oql"], category="reporting", description="Dodaj wpis do logu scenariusza."),
        DslItem(id="error", name="ERROR", dialects=["cql", "oql"], category="reporting", description="Zakończ lub oznacz błąd wykonania."),
        DslItem(id="info", name="INFO", dialects=["cql", "oql"], category="reporting", description="Pokaż informację dla operatora."),
        DslItem(id="api-get", name="API_GET", dialects=["oql"], category="integration", description="Wykonaj żądanie GET."),
        DslItem(id="api-post", name="API_POST", dialects=["oql"], category="integration", description="Wykonaj żądanie POST."),
        DslItem(id="assert-status", name="ASSERT_STATUS", dialects=["oql"], category="assertion", description="Sprawdź kod odpowiedzi HTTP."),
        DslItem(id="assert-json", name="ASSERT_JSON", dialects=["oql"], category="assertion", description="Sprawdź pole JSON w odpowiedzi."),
        DslItem(id="assert-sensor", name="ASSERT_SENSOR", dialects=["oql"], category="assertion", description="Sprawdź odczyt sensora."),
        DslItem(id="assert-valve", name="ASSERT_VALVE", dialects=["oql"], category="assertion", description="Sprawdź stan zaworu."),
        DslItem(id="expect-device", name="EXPECT_DEVICE", dialects=["oql"], category="diagnostics", description="Zweryfikuj obecność urządzenia."),
        DslItem(id="expect-i2c-bus", name="EXPECT_I2C_BUS", dialects=["oql"], category="diagnostics", description="Zweryfikuj magistralę I2C."),
        DslItem(id="expect-i2c-chip", name="EXPECT_I2C_CHIP", dialects=["oql"], category="diagnostics", description="Zweryfikuj układ na I2C."),
        DslItem(id="shell-export", name="SHELL_EXPORT", dialects=["oql"], category="integration", description="Eksportuj wynik do shell."),
        DslItem(id="save-json", name="SAVE_JSON", dialects=["oql"], category="integration", description="Zapisz obiekt JSON do wyniku."),
        DslItem(id="get-sensor", name="GET_SENSOR", dialects=["oql"], category="measurement", description="Pobierz konkretny sensor diagnostyczny."),
    ]

    params = [
        DslItem(id="pressure", name="ciśnienie", dialects=["cql", "oql"], category="measurement", description="Parametr ciśnienia.", type="float", units=["mbar", "bar"]),
        DslItem(id="temperature", name="temperatura", dialects=["cql", "oql"], category="measurement", description="Parametr temperatury.", type="float", units=["°C"]),
        DslItem(id="humidity", name="wilgotność", dialects=["cql", "oql"], category="measurement", description="Parametr wilgotności.", type="float", units=["%"]),
        DslItem(id="flow", name="przepływ", dialects=["cql", "oql"], category="measurement", description="Przepływ medium lub powietrza.", type="float", units=["l/min"]),
        DslItem(id="time", name="czas", dialects=["cql", "oql"], category="control", description="Czas trwania lub timeout.", type="duration", units=["ms", "s", "min"]),
        DslItem(id="status", name="status", dialects=["oql"], category="integration", description="Stan wywołania lub urządzenia.", type="string", units=["bool", "json"]),
        DslItem(id="voltage", name="napięcie", dialects=["oql"], category="measurement", description="Parametr napięcia elektrycznego.", type="float", units=["mV", "V"]),
    ]

    units = [
        DslItem(id="mbar", name="mbar", symbol="mbar", dialects=["cql", "oql"], category="pressure"),
        DslItem(id="bar", name="bar", symbol="bar", dialects=["cql", "oql"], category="pressure"),
        DslItem(id="ms", name="ms", symbol="ms", dialects=["cql", "oql"], category="time"),
        DslItem(id="s", name="s", symbol="s", dialects=["cql", "oql"], category="time"),
        DslItem(id="min", name="min", symbol="min", dialects=["cql", "oql"], category="time"),
        DslItem(id="lmin", name="l/min", symbol="l/min", dialects=["cql", "oql"], category="flow"),
        DslItem(id="degc", name="°C", symbol="°C", dialects=["cql", "oql"], category="temperature"),
        DslItem(id="percent", name="%", symbol="%", dialects=["cql", "oql"], category="ratio"),
        DslItem(id="mv", name="mV", symbol="mV", dialects=["oql"], category="voltage"),
        DslItem(id="v", name="V", symbol="V", dialects=["oql"], category="voltage"),
        DslItem(id="bool", name="bool", symbol="bool", dialects=["oql"], category="state"),
        DslItem(id="json", name="json", symbol="json", dialects=["oql"], category="state"),
    ]

    variables = [
        DslItem(id="runtime-mode", name="runtime.mode", dialects=["oql"], category="state", description="Aktualny tryb uruchomienia interpretera.", type="string"),
        DslItem(id="scenario-id", name="scenario.id", dialects=["cql", "oql"], category="state", description="Identyfikator aktualnego scenariusza.", type="string"),
        DslItem(id="firmware-url", name="firmware.url", dialects=["oql"], category="state", description="Adres firmware API.", type="string"),
        DslItem(id="report-status", name="report.status", dialects=["cql", "oql"], category="reporting", description="Końcowy status raportu.", type="string"),
    ]

    explicit_object_function_map = {
        "pompa": DslFunctionBinding(functions=["SET", "WAIT", "SAVE"]),
        "zawór": DslFunctionBinding(functions=["SET", "WAIT", "ASSERT_VALVE"]),
        "sensor": DslFunctionBinding(functions=["VAL", "MIN", "MAX", "SAMPLE", "FUNC"]),
        "api": DslFunctionBinding(functions=["API_GET", "API_POST", "ASSERT_STATUS", "ASSERT_JSON"]),
        "device": DslFunctionBinding(functions=["EXPECT_DEVICE", "EXPECT_I2C_BUS", "EXPECT_I2C_CHIP", "GET_SENSOR"]),
        "scenario": DslFunctionBinding(functions=["GOTO", "LOG", "WAIT", "ERROR", "INFO"]),
        "shell": DslFunctionBinding(functions=["SHELL_EXPORT", "SAVE_JSON", "LOG"]),
    }

    explicit_param_unit_map = {
        "ciśnienie": DslParamUnitBinding(units=["mbar", "bar"]),
        "temperatura": DslParamUnitBinding(units=["°C"]),
        "wilgotność": DslParamUnitBinding(units=["%"]),
        "przepływ": DslParamUnitBinding(units=["l/min"]),
        "czas": DslParamUnitBinding(units=["ms", "s", "min"]),
        "status": DslParamUnitBinding(units=["bool", "json"]),
        "napięcie": DslParamUnitBinding(units=["mV", "V"]),
    }

    inferred_object_map = _build_inferred_object_function_map(objects, functions)
    inferred_param_map = _build_inferred_param_unit_map(params, units)

    return DslSchema(
        dialects=dialects,
        objects=objects,
        functions=functions,
        params=params,
        units=units,
        variables=variables,
        objectFunctionMap=_merge_object_function_map(explicit_object_function_map, inferred_object_map),
        paramUnitMap=_merge_param_unit_map(explicit_param_unit_map, inferred_param_map),
    )