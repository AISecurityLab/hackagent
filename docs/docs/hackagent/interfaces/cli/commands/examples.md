---
sidebar_label: examples
title: hackagent.interfaces.cli.commands.examples
---

Examples Commands

Launch ready-to-run example scenarios from the CLI.

#### examples

```python
@click.group()
def examples()
```

🧪 Launch built-in examples from the CLI

#### list\_examples

```python
@examples.command(name="list")
@handle_errors
def list_examples()
```

📋 List every example campaign.

#### run\_example

```python
@examples.command(name="run")
@click.argument("name")
@handle_errors
def run_example(name: str)
```

▶ Run one example by name, starting its target if it has one.

#### ollama

```python
@examples.command()
@click.pass_context
@handle_errors
def ollama(ctx)
```

Run the Ollama h4rm3l demo via CLI (no TUI).

#### quick\_evaluation

```python
@examples.command(name="quick-evaluation")
@handle_errors
def quick_evaluation()
```

Run the OpenRouter quick evaluation example (h4rm3l).

#### pc\_tool

```python
@examples.command(name="pc-tool")
@handle_errors
def pc_tool()
```

Run the PC Tool sandbox example: start agent, then launch attack.

#### db\_tool

```python
@examples.command(name="db-tool")
@handle_errors
def db_tool()
```

Run the DB Tool sandbox example: start agent, then launch attack.

#### rag\_example

```python
@examples.command(name="rag")
@handle_errors
def rag_example()
```

Run the RAG indirect-injection example.

#### web\_example

```python
@examples.command(name="web")
@handle_errors
def web_example()
```

Show how to red-team a website chatbot you are authorized to test.

