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
        'getting-started/attack-tutorial',
        'getting-started/datasets-tutorial',
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
        'attacks/advprefix-attacks',
        'attacks/pair-attacks',
        'attacks/baseline-attacks',
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
      label: 'Risks & Evaluation',
      className: 'sidebar-icon sidebar-icon-shield-alert',
      link: {
        type: 'doc',
        id: 'risks/index',
      },
      items: [
        {
          type: 'category',
          label: 'Categories',
          link: {
            type: 'doc',
            id: 'risks/categories/index',
          },
          items: [
            'risks/categories/cybersecurity',
            'risks/categories/data-privacy',
            'risks/categories/fairness',
            'risks/categories/trustworthiness',
            'risks/categories/safety',
            'risks/categories/transparency',
            'risks/categories/third-party',
          ],
        },
        'risks/vulnerabilities',
        'risks/threat-profiles',
        'risks/evaluation-campaigns',
        'risks/custom-vulnerabilities',
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
      label: 'API Reference',
      className: 'sidebar-icon sidebar-icon-code',
      link: {
        type: 'doc',
        id: 'api-index',
      },
      items: [
        'hackagent/agent',
        'hackagent/client', 
        'hackagent/errors',
        {
          type: 'category',
          label: 'Attacks',
          items: [
            'hackagent/attacks/base',
            'hackagent/attacks/orchestrator',
            'hackagent/attacks/registry',
          ],
        },
        {
          type: 'category',
          label: 'Risks',
          link: {
            type: 'doc',
            id: 'risks/index',
          },
          items: [],
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
    {
      type: 'category',
      label: 'Advanced Usage',
      className: 'sidebar-icon sidebar-icon-settings',
      items: [
        'tutorial-extras/manage-docs-versions',
      ],
    },
  ]
};

export default sidebars;
