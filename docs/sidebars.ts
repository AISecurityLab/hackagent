import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

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
      label: '🚀 Getting Started',
      items: [
        'getting-started/installation',
        'getting-started/quick-start',
        'getting-started/attack-tutorial',
      ],
    },
    {
      type: 'category',
      label: '⚔️ Attacks',
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
      label: '📊 Datasets',
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
      label: '🤖 Agents',
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
      label: '🖥️ CLI Reference',
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
      label: ' API Reference',
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
          label: 'Vulnerabilities',
          items: [
            'hackagent/vulnerabilities/prompts',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: '🔐 Security & Ethics',
      items: [
        'security/responsible-disclosure',
        'security/ethical-guidelines',
      ],
    },
    {
      type: 'category',
      label: '🛠️ Advanced Usage',
      items: [
        'tutorial-extras/manage-docs-versions',
      ],
    },
  ]
};

export default sidebars;
