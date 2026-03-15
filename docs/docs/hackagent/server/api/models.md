---
sidebar_label: models
title: hackagent.server.api.models
---

## APITokenLog Objects

```python
class APITokenLog(BaseModel)
```

#### model\_id\_used

Identifier of the AI model used.

#### api\_endpoint

Internal endpoint name, e.g., &#x27;generator&#x27; or &#x27;judge&#x27;.

#### request\_payload\_preview

First ~256 chars of request payload

#### response\_payload\_preview

First ~256 chars of response payload

## AgentRequest Objects

```python
class AgentRequest(BaseModel)
```

#### endpoint

The primary API endpoint URL for interacting with the agent.

#### agent\_type

The specific SDK, ADK, or API type the agent is built upon (e.g., OpenAI SDK, Generic ADK).

#### metadata

Optional JSON data providing specific details and configuration. Structure depends heavily on Agent Type. Examples:
- For GENERIC_ADK: &#123;&#x27;adk_app_name&#x27;: &#x27;my_adk_app&#x27;, &#x27;protocol_version&#x27;: &#x27;1.0&#x27;&#125;
- For OPENAI_SDK: &#123;&#x27;model&#x27;: &#x27;gpt-4-turbo&#x27;, &#x27;api_key_secret_name&#x27;: &#x27;MY_OPENAI_KEY&#x27;, &#x27;instructions&#x27;: &#x27;You are a helpful assistant.&#x27;&#125;
- For GOOGLE_ADK: &#123;&#x27;project_id&#x27;: &#x27;my-gcp-project&#x27;, &#x27;location&#x27;: &#x27;us-central1&#x27;&#125;
- General applicable: &#123;&#x27;version&#x27;: &#x27;1.2.0&#x27;, &#x27;custom_headers&#x27;: &#123;&#x27;X-Custom-Header&#x27;: &#x27;value&#x27;&#125;&#125;

## Attack Objects

```python
class Attack(BaseModel)
```

#### type

A string identifier for the type of attack being configured (e.g., &#x27;PREFIX_GENERATION&#x27;, &#x27;PROMPT_INJECTION&#x27;).

#### configuration

JSON containing client-provided configuration for an attack using this definition.

## AttackRequest Objects

```python
class AttackRequest(BaseModel)
```

#### type

A string identifier for the type of attack being configured (e.g., &#x27;PREFIX_GENERATION&#x27;, &#x27;PROMPT_INJECTION&#x27;).

#### configuration

JSON containing client-provided configuration for an attack using this definition.

## CheckoutSessionRequestRequest Objects

```python
class CheckoutSessionRequestRequest(BaseModel)
```

#### credits\_to\_purchase

Number of credits the user wants to purchase.

## CheckoutSessionResponse Objects

```python
class CheckoutSessionResponse(BaseModel)
```

#### checkout\_url

The URL to redirect the user to for Stripe Checkout.

## ChoiceMessage Objects

```python
class ChoiceMessage(BaseModel)
```

#### role

Role of the message sender

#### content

Generated content

## GenerateErrorResponse Objects

```python
class GenerateErrorResponse(BaseModel)
```

#### error

Description of the error that occurred.

## MessageRequest Objects

```python
class MessageRequest(BaseModel)
```

#### role

Role of the message sender (system, user, assistant)

#### content

Content of the message

## Organization Objects

```python
class Organization(BaseModel)
```

#### credits

Available API credit balance in USD for the organization.

#### credits\_last\_updated

Timestamp of the last credit balance update.

## PatchedAgentRequest Objects

```python
class PatchedAgentRequest(BaseModel)
```

#### endpoint

The primary API endpoint URL for interacting with the agent.

#### agent\_type

The specific SDK, ADK, or API type the agent is built upon (e.g., OpenAI SDK, Generic ADK).

#### metadata

Optional JSON data providing specific details and configuration. Structure depends heavily on Agent Type. Examples:
- For GENERIC_ADK: &#123;&#x27;adk_app_name&#x27;: &#x27;my_adk_app&#x27;, &#x27;protocol_version&#x27;: &#x27;1.0&#x27;&#125;
- For OPENAI_SDK: &#123;&#x27;model&#x27;: &#x27;gpt-4-turbo&#x27;, &#x27;api_key_secret_name&#x27;: &#x27;MY_OPENAI_KEY&#x27;, &#x27;instructions&#x27;: &#x27;You are a helpful assistant.&#x27;&#125;
- For GOOGLE_ADK: &#123;&#x27;project_id&#x27;: &#x27;my-gcp-project&#x27;, &#x27;location&#x27;: &#x27;us-central1&#x27;&#125;
- General applicable: &#123;&#x27;version&#x27;: &#x27;1.2.0&#x27;, &#x27;custom_headers&#x27;: &#123;&#x27;X-Custom-Header&#x27;: &#x27;value&#x27;&#125;&#125;

## PatchedAttackRequest Objects

```python
class PatchedAttackRequest(BaseModel)
```

#### type

A string identifier for the type of attack being configured (e.g., &#x27;PREFIX_GENERATION&#x27;, &#x27;PROMPT_INJECTION&#x27;).

#### configuration

JSON containing client-provided configuration for an attack using this definition.

## PatchedResultRequest Objects

```python
class PatchedResultRequest(BaseModel)
```

#### request\_payload

Payload sent to agent or relevant data for client-submitted results.

## ResultRequest Objects

```python
class ResultRequest(BaseModel)
```

#### request\_payload

Payload sent to agent or relevant data for client-submitted results.

## Usage Objects

```python
class Usage(BaseModel)
```

#### prompt\_tokens

Number of tokens in the prompt

#### completion\_tokens

Number of tokens in the completion

#### total\_tokens

Total tokens used

## UserAPIKeyRequest Objects

```python
class UserAPIKeyRequest(BaseModel)
```

#### name

A human-readable name for the API key.

## UserProfile Objects

```python
class UserProfile(BaseModel)
```

#### auth0\_user\_id

The unique user identifier (sub claim) provided by Auth0.

## Agent Objects

```python
class Agent(BaseModel)
```

#### endpoint

The primary API endpoint URL for interacting with the agent.

#### agent\_type

The specific SDK, ADK, or API type the agent is built upon (e.g., OpenAI SDK, Generic ADK).

#### metadata

Optional JSON data providing specific details and configuration. Structure depends heavily on Agent Type. Examples:
- For GENERIC_ADK: &#123;&#x27;adk_app_name&#x27;: &#x27;my_adk_app&#x27;, &#x27;protocol_version&#x27;: &#x27;1.0&#x27;&#125;
- For OPENAI_SDK: &#123;&#x27;model&#x27;: &#x27;gpt-4-turbo&#x27;, &#x27;api_key_secret_name&#x27;: &#x27;MY_OPENAI_KEY&#x27;, &#x27;instructions&#x27;: &#x27;You are a helpful assistant.&#x27;&#125;
- For GOOGLE_ADK: &#123;&#x27;project_id&#x27;: &#x27;my-gcp-project&#x27;, &#x27;location&#x27;: &#x27;us-central1&#x27;&#125;
- General applicable: &#123;&#x27;version&#x27;: &#x27;1.2.0&#x27;, &#x27;custom_headers&#x27;: &#123;&#x27;X-Custom-Header&#x27;: &#x27;value&#x27;&#125;&#125;

## Choice Objects

```python
class Choice(BaseModel)
```

#### index

Index of the choice

#### message

Message object

#### finish\_reason

Reason for completion (stop, length, etc.)

## GenerateRequestRequest Objects

```python
class GenerateRequestRequest(BaseModel)
```

#### model

Client-specified model (will be overridden by server)

#### messages

Array of conversation messages

#### stream

Whether to stream the response

#### temperature

Sampling temperature (0-2)

#### max\_tokens

Maximum tokens to generate

#### top\_p

Nucleus sampling threshold

#### frequency\_penalty

Frequency penalty (-2.0 to 2.0)

#### presence\_penalty

Presence penalty (-2.0 to 2.0)

#### stop

Sequences where the API will stop generating

## GenerateSuccessResponse Objects

```python
class GenerateSuccessResponse(BaseModel)
```

#### id

Unique identifier for the completion

#### object

Object type (chat.completion)

#### created

Unix timestamp of creation

#### model

Model used for generation

#### choices

Array of completion choices

#### usage

Token usage information

## PatchedRunRequest Objects

```python
class PatchedRunRequest(BaseModel)
```

#### attack

The Attack this run is an instance of, if applicable.

#### run\_config

JSON containing specific settings for this run. If linked to an Attack, this might be a copy or subset of its configuration.

## Result Objects

```python
class Result(BaseModel)
```

#### request\_payload

Payload sent to agent or relevant data for client-submitted results.

## Run Objects

```python
class Run(BaseModel)
```

#### attack

The Attack this run is an instance of, if applicable.

#### run\_config

JSON containing specific settings for this run. If linked to an Attack, this might be a copy or subset of its configuration.

#### is\_client\_executed

Indicates if the run was initiated via an Attack by a client application.

## RunRequest Objects

```python
class RunRequest(BaseModel)
```

#### attack

The Attack this run is an instance of, if applicable.

#### run\_config

JSON containing specific settings for this run. If linked to an Attack, this might be a copy or subset of its configuration.

## UserAPIKey Objects

```python
class UserAPIKey(BaseModel)
```

#### name

A human-readable name for the API key.

#### revoked

If the API key is revoked, clients cannot use it anymore. (This cannot be undone.)

#### expiry\_date

Once API key expires, clients cannot use it anymore.

#### ResultListEvaluationStatus

Alias used by api/result/result_list.py for the evaluation_status filter.

#### RunListStatus

Alias used by api/run/run_list.py for the status filter.

## KeyContextRetrieveResponse200 Objects

```python
class KeyContextRetrieveResponse200(BaseModel)
```

Response body for GET /key/context — caller identity context.

