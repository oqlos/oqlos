# oqlos-core

Parser, interpreter runtime, and event store for OQL. Historical Python symbols
remain compatibility adapters, not names of a supported public language.

```python
from oqlos.core.oql_document import parse_oql_document, validate_oql_document
from oqlos.core.interpreter import OqlInterpreter
from oqlos.shared.event_store import EventStore
```

Hardware execute mode / firmware bridges: `pip install 'oqlos-core[firmware]>=0.2.1'`
