# oqlos-core

Parser, interpreter runtime, and event store for OqlOS (CQL + OQL v3/v4).

```python
from oqlos.core.cql_parser import parse_cql, validate_cql
from oqlos.core.interpreter import CqlInterpreter
from oqlos.shared.event_store import EventStore
```

Hardware execute mode / firmware bridges: `pip install 'oqlos-core[firmware]>=0.2.1'`
