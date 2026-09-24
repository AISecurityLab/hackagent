---
sidebar_label: agent
title: hackagent.interfaces.cli.commands.agent
---

Agent Commands
Manage AI agents registered with HackAgent.

#### agent

```python
@click.group()
def agent()
```

🤖 Manage AI agents

#### list

```python
@agent.command()
@click.pass_context
@handle_errors
def list(ctx)
```

List registered agents

#### create

```python
@agent.command()
@click.option("--name", required=True, help="Agent name")
@click.option(
    "--type",
    "agent_type",
    type=click.Choice(["google-adk", "litellm", "openai-sdk", "ollama"]),
    required=True,
    help="Agent type",
)
@click.option("--endpoint", required=True, help="Agent endpoint URL")
@click.option("--description", help="Agent description")
@click.option("--metadata", help="Additional metadata as JSON string")
@click.pass_context
@handle_errors
def create(ctx, name, agent_type, endpoint, description, metadata)
```

Create a new agent

#### show

```python
@agent.command()
@click.argument("agent_id")
@click.pass_context
@handle_errors
def show(ctx, agent_id)
```

Show detailed information about an agent

#### update

```python
@agent.command()
@click.argument("agent_id")
@click.option("--name", help="New agent name")
@click.option("--endpoint", help="New agent endpoint")
@click.option("--description", help="New agent description")
@click.option("--metadata", help="New metadata as JSON string")
@click.pass_context
@handle_errors
def update(ctx, agent_id, name, endpoint, description, metadata)
```

Update an existing agent

#### delete

```python
@agent.command()
@click.argument("agent_id")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
@handle_errors
def delete(ctx, agent_id, confirm)
```

Delete an agent

#### test

```python
@agent.command()
@click.argument("agent_name")
@click.pass_context
@handle_errors
def test(ctx, agent_name)
```

Test connection to an agent

This command attempts to establish a connection with the specified agent
to verify it&#x27;s accessible and responding.

