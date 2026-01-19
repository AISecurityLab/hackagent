---
sidebar_position: 5
---

# Custom Providers

Extend HackAgent with custom dataset providers for proprietary data sources.

## Creating a Provider

Subclass `DatasetProvider` and implement required methods:

```python
from hackagent.datasets import DatasetProvider, register_provider
from typing import Any, Dict, List, Optional

class MyDatabaseProvider(DatasetProvider):
    """Load goals from a custom database."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_string = config.get("connection_string")
        self.table = config.get("table", "goals")
        self.goal_column = config.get("goal_column", "text")

    def load_goals(
        self,
        limit: Optional[int] = None,
        **kwargs,
    ) -> List[str]:
        """Load goals from the database."""
        # Connect to your database
        conn = my_db_connect(self.connection_string)
        
        query = f"SELECT {self.goal_column} FROM {self.table}"
        if limit:
            query += f" LIMIT {limit}"
        
        results = conn.execute(query).fetchall()
        return [row[0] for row in results if row[0]]

    def get_metadata(self) -> Dict[str, Any]:
        """Return provider metadata."""
        return {
            "provider": "my_database",
            "table": self.table,
            "goal_column": self.goal_column,
        }
```

---

## Registering the Provider

```python
from hackagent.datasets import register_provider

# Register with a unique name
register_provider("my_database", MyDatabaseProvider)
```

---

## Using the Custom Provider

Once registered, use it like any other provider:

```python
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "provider": "my_database",
        "connection_string": "postgresql://localhost/safety_tests",
        "table": "harmful_prompts",
        "goal_column": "prompt_text",
        "limit": 100,
    }
}

agent.hack(attack_config=attack_config)
```

---

## Provider Interface

### Required Methods

| Method | Description |
|--------|-------------|
| `load_goals(limit, **kwargs)` | Load and return list of goal strings |
| `get_metadata()` | Return metadata dictionary |

### Inherited Helper

Use `_extract_goal_from_record()` for consistent field extraction:

```python
def load_goals(self, limit=None, **kwargs):
    records = self._fetch_records()
    goals = []
    
    for record in records:
        goal = self._extract_goal_from_record(
            record,
            goal_field=self.goal_field,
            fallback_fields=["prompt", "text", "input"],
        )
        if goal:
            goals.append(goal)
    
    return goals[:limit] if limit else goals
```

---

## Example: API Provider

```python
import requests
from hackagent.datasets import DatasetProvider, register_provider

class APIProvider(DatasetProvider):
    """Load goals from a REST API."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config["base_url"]
        self.api_key = config.get("api_key")
        self.goal_field = config.get("goal_field", "text")

    def load_goals(self, limit=None, **kwargs):
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        params = {"limit": limit} if limit else {}
        
        response = requests.get(
            f"{self.base_url}/goals",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        
        data = response.json()
        return [item[self.goal_field] for item in data if item.get(self.goal_field)]

    def get_metadata(self):
        return {"provider": "api", "base_url": self.base_url}

# Register it
register_provider("api", APIProvider)

# Use it
attack_config = {
    "dataset": {
        "provider": "api",
        "base_url": "https://my-api.example.com",
        "api_key": "sk-...",
        "goal_field": "prompt",
    }
}
```
