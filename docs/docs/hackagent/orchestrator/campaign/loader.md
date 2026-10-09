---
sidebar_label: loader
title: hackagent.orchestrator.campaign.loader
---

Load declarative campaigns from YAML or already-decoded mappings.

#### load\_campaign

```python
def load_campaign(source: str | Path | Mapping[str, Any]) -> CampaignSpec
```

Validate and return one campaign specification.

