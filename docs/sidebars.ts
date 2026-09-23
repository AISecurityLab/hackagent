import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';
/**
 * Creating a sidebar allows you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation

 The sidebars can be generated from the filesystem, or explicitly defined here.

 Create as many sidebars as you want.
 */
const sidebars: SidebarsConfig = {
  // By default, Docusaurus generates a sidebar from the docs folder structure
  tutorialSidebar: [
    'introduction',
    {
      type: 'category',
      label: 'Getting Started',
      className: 'sidebar-icon sidebar-icon-rocket',
      items: [
        'getting-started/installation',
        'getting-started/quick-start',
        'getting-started/quick-security-scan',
        'getting-started/attack-tutorial',
        'getting-started/datasets-tutorial',
      ],
    },
    {
      type: 'category',
      label: 'AI Risks',
      className: 'sidebar-icon sidebar-icon-shield-alert',
      link: {
        type: 'doc',
        id: 'risks/index',
      },
      items: [
        {
          type: 'category',
          label: 'Vulnerabilities',
          link: {
            type: 'doc',
            id: 'risks/vulnerabilities',
          },
          items: [
            'risks/vulnerabilities/jailbreak',
            'risks/vulnerabilities/prompt-injection',
            'risks/vulnerabilities/system-prompt-leakage',
            'risks/vulnerabilities/input-manipulation-attack',
            'risks/vulnerabilities/model-evasion',
            'risks/vulnerabilities/craft-adversarial-data',
            'risks/vulnerabilities/sensitive-information-disclosure',
            'risks/vulnerabilities/misinformation',
            'risks/vulnerabilities/excessive-agency',
            'risks/vulnerabilities/malicious-tool-invocation',
            'risks/vulnerabilities/credential-exposure',
            'risks/vulnerabilities/public-facing-application-exploitation',
            'risks/vulnerabilities/vector-embedding-weaknesses-exploit',
          ],
        },
        'risks/custom-vulnerabilities',
        {
          type: 'category',
          label: 'Evaluation Campaigns',
          link: {
            type: 'doc',
            id: 'risks/evaluation-campaigns',
          },
          items: [
            'risks/evaluation-campaigns/quick-scan',
            'risks/evaluation-campaigns/comprehensive-audit',
            'risks/evaluation-campaigns/targeted-assessment',
            'risks/evaluation-campaigns/custom-campaigns',
          ],
        },
        {
          type: 'doc',
          id: 'risks/indirect-prompt-injection',
          label: 'Indirect Prompt Injection',
        },
      ],
    },
    {
      type: 'category',
      label: 'Attacks',
      className: 'sidebar-icon sidebar-icon-sword',
      link: {
        type: 'doc',
        id: 'attacks/index',
      },
      items: [
        'attacks/taxonomy',
        'attacks/shared-args',
        {
          type: 'category',
          label: 'Jailbreak',
          items: [
            {
              type: 'category',
              label: 'Static',
              collapsed: false,
              items: [
                'attacks/baseline',
                'attacks/static-template',
                'attacks/flipattack',
                'attacks/cipherchat',
                'attacks/h4rm3l',
                'attacks/mml',
                'attacks/fc',
                'attacks/tfc',
              ],
            },
            {
              type: 'category',
              label: 'Adaptive',
              collapsed: false,
              items: [
                'attacks/pair',
                'attacks/tap',
                'attacks/pap',
                'attacks/bon',
                'attacks/advprefix',
                'attacks/autodan_turbo',
              ],
            },
            {
              type: 'category',
              label: 'Multi-turn',
              collapsed: false,
              items: [
                'attacks/crescendo',
              ],
            },
          ],
        },
        {
          type: 'category',
          label: 'Indirect Injection',
          items: [
            'attacks/rag',
            'attacks/tool_output_ipi',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'Datasets',
      className: 'sidebar-icon sidebar-icon-database',
      link: {
        type: 'doc',
        id: 'datasets/index',
      },
      items: [
        'datasets/selecting-intent-categories',
        'datasets/presets',
        'datasets/huggingface',
        'datasets/url-json',
        'datasets/file',
        'datasets/custom-providers',
        'datasets/troubleshooting',
      ],
    },
    {
      type: 'category',
      label: 'Agents',
      className: 'sidebar-icon sidebar-icon-cpu',
      link: {
        type: 'doc',
        id: 'agents/index',
      },
      items: [
        {
          type: 'doc',
          id: 'agents/ollama',
          label: 'Ollama',
        },
        {
          type: 'doc',
          id: 'agents/openai-sdk',
          label: 'OpenAI SDK',
        },
        {
          type: 'doc',
          id: 'agents/google-adk',
          label: 'Google ADK',
        },
        {
          type: 'doc',
          id: 'agents/claude-code',
          label: 'Claude Code',
        },
        {
          type: 'doc',
          id: 'agents/codex',
          label: 'Codex',
        },
        {
          type: 'doc',
          id: 'agents/hermes',
          label: 'Hermes Agent',
        },
        {
          type: 'doc',
          id: 'agents/guardrails',
          label: 'Guardrails',
        },
      ],
    },
    {
      type: 'category',
      label: 'CLI Reference',
      className: 'sidebar-icon sidebar-icon-terminal',
      items: [
        'cli/overview',
        'cli/initialization',
        'cli/config',
        'cli/agent',
        'cli/attack',
        'cli/scan',
        'cli/results',
        'cli/datasets',
        'cli/web',
      ],
    },
    {
      type: 'category',
      label: 'SDK Reference',
      className: 'sidebar-icon sidebar-icon-code',
      link: {
        type: 'doc',
        id: 'api-index',
      },
      items: [
        'hackagent/agent',
        {
          type: 'category',
          label: 'Core',
          items: [
            'hackagent/core/settings',
            'hackagent/core/contracts',
            'hackagent/core/errors',
            'hackagent/core/logging',
            'hackagent/core/async_utils',
          ],
        },
        {
          type: 'category',
          label: 'Models',
          items: [
            'hackagent/models/client',
            'hackagent/models/dispatch',
            'hackagent/models/factory',
            'hackagent/models/guardrail',
            'hackagent/models/envelope',
            'hackagent/models/provider_config',
            {
              type: 'category',
              label: 'Adapters',
              items: [
                'hackagent/models/adapters/base',
                'hackagent/models/adapters/cli_agent',
                'hackagent/models/adapters/adk',
                'hackagent/models/adapters/claude',
                'hackagent/models/adapters/codex',
                'hackagent/models/adapters/hermes',
                'hackagent/models/adapters/web',
                'hackagent/models/adapters/browser',
                'hackagent/models/adapters/litellm_callbacks',
              ],
            },
          ],
        },
        {
          type: 'category',
          label: 'Tracking',
          items: [
            'hackagent/router/tracking/tracker',
            'hackagent/router/tracking/coordinator',
            'hackagent/router/tracking/context',
            'hackagent/router/tracking/step',
            'hackagent/router/tracking/decorators',
            'hackagent/router/tracking/utils',
          ],
        },
        {
          type: 'category',
          label: 'Attacks',
          items: [
            'hackagent/attacks/orchestrator',
            'hackagent/attacks/registry',
            {
              type: 'category',
              label: 'Evaluator',
              items: [
                'hackagent/attacks/evaluator/base',
                'hackagent/attacks/evaluator/evaluation_step',
                'hackagent/attacks/evaluator/inline_step_judge',
                'hackagent/attacks/evaluator/judge_evaluators',
                'hackagent/attacks/evaluator/pattern_evaluators',
                'hackagent/attacks/evaluator/metrics',
                'hackagent/attacks/evaluator/sync',
              ],
            },
            {
              type: 'category',
              label: 'Techniques',
              items: [
                'hackagent/attacks/techniques/base',
                'hackagent/attacks/techniques/baseline/attack',
                'hackagent/attacks/techniques/static_template/attack',
                'hackagent/attacks/techniques/flipattack/attack',
                'hackagent/attacks/techniques/bon/attack',
                'hackagent/attacks/techniques/cipherchat/attack',
                'hackagent/attacks/techniques/h4rm3l/attack',
                'hackagent/attacks/techniques/mml/attack',
                'hackagent/attacks/techniques/fc/attack',
                'hackagent/attacks/techniques/pap/attack',
                'hackagent/attacks/techniques/pair/attack',
                'hackagent/attacks/techniques/crescendo/attack',
                'hackagent/attacks/techniques/tap/attack',
                'hackagent/attacks/techniques/advprefix/attack',
                'hackagent/attacks/techniques/autodan_turbo/attack',
                'hackagent/attacks/techniques/rag/attack',
              ],
            },
          ],
        },
        {
          type: 'category',
          label: 'Datasets',
          items: [
            'hackagent/datasets/base',
            'hackagent/datasets/presets',
            'hackagent/datasets/registry',
            'hackagent/datasets/providers/file',
            'hackagent/datasets/providers/huggingface',
            'hackagent/datasets/providers/url_json',
          ],
        },
        {
          type: 'category',
          label: 'Catalog',
          items: [
            'hackagent/catalog/taxonomy',
            'hackagent/catalog/risks/base',
            'hackagent/catalog/risks/profile_types',
            'hackagent/catalog/risks/profile_helpers',
            'hackagent/catalog/risks/registry',
            'hackagent/catalog/risks/utils',
          ],
        },
        {
          type: 'category',
          label: 'Storage',
          items: [
            'hackagent/storage/store',
            'hackagent/storage/records',
            'hackagent/storage/local',
            'hackagent/storage/remote',
            'hackagent/storage/buckets',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'Security & Ethics',
      className: 'sidebar-icon sidebar-icon-lock',
      items: [
        'security/responsible-disclosure',
        'security/ethical-guidelines',
      ],
    },
  ]
};

export default sidebars;
