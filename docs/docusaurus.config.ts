import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'HackAgent',
  tagline: 'Test the security of your agents and models',
  favicon: 'img/favicon.ico',

  // Set the production url of your site here
  url: 'https://hackagent.dev',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For local development, use '/' to serve at root
  // For production, you can change this to '/docs/' if needed
  baseUrl: '/',
  trailingSlash: false,

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'vista-labs', // Usually your GitHub org/user name.
  projectName: 'hackagent', // Usually your repo name.

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

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
  },
  themes: ['@docusaurus/theme-mermaid'],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
          editUrl: 'https://github.com/vistalabs-org/hackagent',
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
      } satisfies Preset.Options,
    ],
  ],

  plugins: [],

  themeConfig: {
    // Mermaid theme configuration
    mermaid: {
      theme: {light: 'neutral', dark: 'dark'},
    },
    announcementBar: {
      id: 'github_star', // Any unique ID for this banner
      content:
        '<b>Like our product? Please <a target="_blank" rel="noopener noreferrer" href="https://github.com/vistalabs-org/hackagent">leave a star on the GitHub repo</a>!</b>',
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
        href: 'https://hackagent.dev',
        target: '_blank',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://github.com/vistalabs-org/hackagent',
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
          title: 'Community',
          items: [
            {
              label: 'Discord',
              href: 'https://discord.gg/BBJkTStF4h',
            },
            {
              label: 'X',
              href: 'https://x.com/vistalabsai',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/vistalabs-org',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Vista Labs, Ltd.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
