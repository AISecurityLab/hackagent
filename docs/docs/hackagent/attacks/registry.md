---
sidebar_label: registry
title: hackagent.attacks.registry
---

Attack technique registry.

This module registers all available attack techniques as concrete orchestrators
using a factory function to eliminate boilerplate code.

The factory dynamically creates orchestrator classes that configure:
- attack_type: String identifier for the attack
- attack_impl_class: BaseAttack subclass implementing the algorithm
- Custom methods: Optional specialized behavior (e.g., PAIR&#x27;s attacker setup)

To add a new attack:
1. Implement BaseAttack subclass in techniques/your_attack/
2. Register here using create_orchestrator()
3. Add to ATTACK_REGISTRY dict

#### create\_orchestrator

```python
def create_orchestrator(
        attack_name: str,
        attack_impl_class: Type[BaseAttack],
        custom_setup: Optional[Callable] = None) -> Type[AttackOrchestrator]
```

Factory function to create orchestrator classes dynamically.

This eliminates repetitive class definitions while maintaining clean
architecture separation between orchestration and attack algorithms.

**Arguments**:

- `attack_name` - Attack identifier (e.g., &quot;AdvPrefix&quot;)
- `attack_impl_class` - BaseAttack subclass implementing the technique
- `custom_setup` - Optional method for specialized kwargs preparation
- `Signature` - (self, attack_config, run_config_override) -&gt; Dict[str, Any]
  

**Returns**:

  Orchestrator class configured for this attack technique
  

**Example**:

  &gt;&gt;&gt; MyOrchestrator = create_orchestrator(&quot;MyAttack&quot;, MyAttackClass)
  &gt;&gt;&gt; orchestrator = MyOrchestrator(hack_agent)
  &gt;&gt;&gt; results = orchestrator.execute(attack_config)

