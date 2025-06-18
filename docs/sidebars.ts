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
    'intro',
    'HowTo',
    {
      type: 'category',
      label: '🚀 Getting Started',
      items: [
        'tutorial-basics/AdvPrefix',
      ],
    },
        {
      type: 'category',
      label: '🔧 SDK Reference',
      items: [
        'sdk/python-quickstart',
      ],
    },
    {
      type: 'category',
      label: '🔗 API Reference',
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
            'hackagent/attacks/strategies',
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
      label: '⚔️ Attack Types',
      items: [
        'attacks/advprefix-attacks',
      ],
    },
    {
      type: 'category',
      label: '🔌 Integrations',
      items: [
        'integrations/google-adk',
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
  ],

  // But you can create a sidebar manually
  /*
  tutorialSidebar: [
    'intro',
    'hello',
    {
      type: 'category',
      label: 'Tutorial',
      items: ['tutorial-basics/create-a-document'],
    },
  ],
   */
};

export default sidebars;
