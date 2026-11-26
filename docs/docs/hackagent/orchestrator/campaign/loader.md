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

A file may name API keys only as `${VARIABLE}` references; a mapping
built in Python may also carry key values.

**Arguments**:

- `source` - Path of a YAML campaign file, or the decoded mapping.
  

**Returns**:

  The validated campaign.
  

**Raises**:

- `FileNotFoundError` - When the path is not a file.
- `ValueError` - When the YAML cannot be parsed or is not a mapping.
- `CampaignInvalid` - When it does not validate (a `ValueError`): its
  `issues` say what is wrong, each where it is.
- `CredentialError` - When a file contains a literal API key.
  

**Example**:

  Load a file and inspect it before running:
  
    ```python
    from hackagent.orchestrator.campaign import load_campaign

    spec = load_campaign("campaign.yaml")
    print(spec.campaign.name, [attack.name for attack in spec.attacks])
    ```

#### load\_stored\_campaign

```python
def load_stored_campaign(data: Mapping[str, Any]) -> CampaignSpec
```

Validate a stored campaign, keeping its `${VARIABLE}` references.

A key is read from its variable when the model that uses it is built, so
the campaign can be checked where its variables are not set and executed
where they are. Raises `CredentialError` for an `api_key` that is not
a reference, without repeating its value.

