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
        'getting-started/dashboard',
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
          type: 'doc',
          id: 'risks/vulnerabilities',
          label: 'Jailbreak',
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
        'attacks/advprefix',
        'attacks/autodan_turbo',
        'attacks/pair',
        'attacks/tap',
        'attacks/flipattack',
        'attacks/bon',
        'attacks/h4rm3l',
        'attacks/cipherchat',
        'attacks/pap',
        'attacks/baseline',
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
        'datasets/presets',
        'datasets/huggingface',
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
        'cli/attack',
        'cli/results',
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
        'hackagent/errors',
        'hackagent/logger',
        'hackagent/utils',
        {
          type: 'category',
          label: 'Router',
          items: [
            'hackagent/router/router',
            'hackagent/router/types',
            {
              type: 'category',
              label: 'Adapters',
              items: [
                'hackagent/router/adapters/base',
                'hackagent/router/adapters/openai',
                'hackagent/router/adapters/ollama',
                'hackagent/router/adapters/litellm',
                'hackagent/router/adapters/google_adk',
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
          ],
        },
        {
          type: 'category',
          label: 'Attacks',
          items: [
            'hackagent/attacks/base',
            'hackagent/attacks/orchestrator',
            'hackagent/attacks/registry',
            {
              type: 'category',
              label: 'Evaluator',
              items: [
                'hackagent/attacks/evaluator/base',
                'hackagent/attacks/evaluator/evaluation_step',
                'hackagent/attacks/evaluator/judge_evaluators',
                'hackagent/attacks/evaluator/pattern_evaluators',
                'hackagent/attacks/evaluator/metrics',
              ],
            },
            {
              type: 'category',
              label: 'Techniques',
              items: [
                'hackagent/attacks/techniques/base',
                'hackagent/attacks/techniques/advprefix/attack',
                'hackagent/attacks/techniques/pair/attack',
                'hackagent/attacks/techniques/tap/attack',
                'hackagent/attacks/techniques/bon/attack',
                'hackagent/attacks/techniques/flipattack/attack',
                'hackagent/attacks/techniques/autodan_turbo/attack',
                'hackagent/attacks/techniques/baseline/attack',
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
          ],
        },
        {
          type: 'category',
          label: 'Risks',
          items: [
            'hackagent/risks/base',
            'hackagent/risks/profile_types',
            'hackagent/risks/profile_helpers',
            'hackagent/risks/registry',
            'hackagent/risks/utils',
          ],
        },
        {
          type: 'category',
          label: 'Server',
          items: [
            'hackagent/server/client',
            'hackagent/server/types',
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
