# oqlos-core

Parser, interpreter runtime, and event store for OQL. Historical Python symbol
names such as `parse_cql` and `CqlInterpreter` are compatibility adapters, not
names of a supported public scenario language.

```python
from oqlos.core.cql_parser import parse_cql, validate_cql
from oqlos.core.interpreter import OqlInterpreter
from oqlos.shared.event_store import EventStore
```

Hardware execute mode / firmware bridges: `pip install 'oqlos-core[firmware]>=0.2.1'`
