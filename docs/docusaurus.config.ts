import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'HackAgent',
  tagline: 'Test the security of your agents and models',
  favicon: 'img/favicon.ico',

  // Set the production url of your site here
  url: 'https://animated-guide-g46k62k.pages.github.io',
  // Set the /<baseUrl>/ pathname under which your site is served
  baseUrl: '/',
  trailingSlash: false,

  // GitHub pages deployment config.
  organizationName: 'AISecurityLab', // Usually your GitHub org/user name.
  projectName: 'HackAgent', // Must match the GitHub repo name exactly (case-sensitive).

  onBrokenLinks: 'throw',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  // Enable Mermaid diagrams
  markdown: {
    mermaid: true,
    // Use extension-based parsing: .md as CommonMark, .mdx as MDX.
    // This avoids MDX parsing errors in generated API docs while preserving JSX support
    // for authored pages explicitly saved as .mdx.
    format: 'detect',
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
  themes: [
    '@docusaurus/theme-mermaid',
    // Offline search: builds a Lucene index at build time and ships it with the
    // site. No external service and no API keys, so it works on any host.
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      {
        hashed: true,
        // routeBasePath is '/', so the docs live at the site root.
        docsRouteBasePath: '/',
        indexBlog: false,
        highlightSearchTermsOnTargetPage: true,
        searchResultLimits: 10,
        explicitSearchResultPath: true,
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
          editUrl: 'https://github.com/AISecurityLab/hackagent/edit/main/docs/',
          // The docs plugin passes `exclude` to globby `ignore`, which does
          // not honor `!` negation. Drop the default `**/_*/**` rule so the
          // generated `hackagent/attacks/_lib` pages are published. Files
          // named `_*.md` (partials, `_version.md`) stay excluded.
          exclude: ['**/_*.{js,jsx,ts,tsx,md,mdx}'],
          // Enable versioning for API docs
          includeCurrentVersion: true,
          lastVersion: 'current',
          versions: {
            current: {
              label: 'Latest (Development)',
              path: '/',
            },
          },
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
        gtag: {
          trackingID: 'G-2P6K2HWVEE',
          anonymizeIP: true,
        },
      } satisfies Preset.Options,
    ],
  ],

  plugins: [
    [
      '@docusaurus/plugin-client-redirects',
      {
        // Technique API pages moved under their category folder
        // (static/, adaptive/, multi_turn/, indirect/).
        createRedirects(existingPath: string) {
          const moved = existingPath.match(
            /^\/hackagent\/attacks\/techniques\/(?:static|adaptive|multi_turn|indirect)\/(.+)$/,
          );
          return moved ? [`/hackagent/attacks/techniques/${moved[1]}`] : undefined;
        },
        redirects: [
          {
            from: '/hackagent/attacks/evaluator/base',
            to: '/hackagent/evaluation/base',
          },
          {
            from: '/hackagent/attacks/evaluator/judge_evaluators',
            to: '/hackagent/evaluation/judges',
          },
          {
            from: '/hackagent/attacks/evaluator/pattern_evaluators',
            to: '/hackagent/evaluation/patterns',
          },
          {
            from: '/hackagent/attacks/evaluator/metrics',
            to: '/hackagent/evaluation/metrics',
          },
          {
            from: [
              '/hackagent/attacks/evaluator/evaluation_step',
              '/hackagent/attacks/evaluator/sync',
            ],
            to: '/evaluation',
          },
          {
            from: '/hackagent/attacks/evaluator/inline_step_judge',
            to: '/hackagent/attacks/_lib/inline_judge',
          },
          {
            from: '/hackagent/router/tracking/tracker',
            to: '/hackagent/tracking/tracker',
          },
          {
            from: '/hackagent/router/tracking/coordinator',
            to: '/hackagent/tracking/coordinator',
          },
          {
            from: '/hackagent/router/tracking/context',
            to: '/hackagent/tracking/context',
          },
          {
            from: '/hackagent/router/tracking/step',
            to: '/hackagent/tracking/step',
          },
          {
            from: '/hackagent/router/tracking/decorators',
            to: '/hackagent/tracking/decorators',
          },
          {
            from: '/hackagent/router/tracking/utils',
            to: '/hackagent/tracking/utils',
          },
          {
            from: '/hackagent/router/tracking/audit',
            to: '/hackagent/tracking/audit',
          },
          {
            from: '/hackagent/router/tracking/category_classifier',
            to: '/tracking',
          },
          {
            from: '/hackagent/attacks/orchestrator',
            to: '/orchestrator',
          },
          {
            from: '/hackagent/attacks/registry',
            to: '/hackagent/orchestrator/registry',
          },
          {
            from: '/hackagent/router/discovery/scanner',
            to: '/hackagent/orchestrator/planning',
          },
          {
            from: '/hackagent/agent',
            to: '/hackagent/client',
          },
        ],
      },
    ],
  ],

  themeConfig: {
    // Color mode configuration
    colorMode: {
      defaultMode: 'dark',
      disableSwitch: false,
      respectPrefersColorScheme: true,
    },
    // Mermaid theme configuration
    mermaid: {
      theme: {light: 'neutral', dark: 'dark'},
      options: {
        securityLevel: 'loose',
        flowchart: {
          useMaxWidth: false,
          htmlLabels: false,
        },
        sequence: {
          useMaxWidth: false,
        },
      },
    },
    announcementBar: {
      id: 'github_star', // Any unique ID for this banner
      content:
        '<b>Like our product? Please <a target="_blank" rel="noopener noreferrer" href="https://github.com/AISecurityLab/hackagent">leave a star on the GitHub repo</a>!</b>',
      backgroundColor: '#FFA500', // Change background to orange
      textColor: '#000000', // Adjust text color for contrast if needed (e.g., black)
      isCloseable: true, // Defaults to `true`
    },
    // Replace with your project's social card
    image: 'img/docusaurus-social-card.jpg',
    navbar: {
      title: 'HackAgent',
      logo: {
        alt: 'HackAgent Logo',
        src: 'img/logo.png',
        href: '/',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://github.com/AISecurityLab/hackagent',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Docs',
              to: '/',
            },
          ],
        },
        {
          title: 'Contacts',
          items: [
            {
              label: 'LinkedIn',
              href: 'https://www.linkedin.com/company/ai4industry/',
            },
            {
              label: 'Website',
              href: 'https://ai4i.it',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/AISecurityLab/hackagent',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} [AI4I](https://ai4i.it).`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'json', 'python', 'yaml', 'toml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
