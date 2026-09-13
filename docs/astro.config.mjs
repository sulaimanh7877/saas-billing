// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

const repository = 'https://github.com/sulaimanh7877/saas-billing';
const base = '/saas-billing';

// https://astro.build/config
export default defineConfig({
	site: 'https://sulaimanh7877.github.io',
	base,
	integrations: [
		starlight({
			title: 'Billing & Channel Engine',
			description:
				'Self-hostable billing, subscriptions, entitlements, audit, analytics, and channel/partner sales for any SaaS.',
			logo: {
				src: './src/assets/logo.svg',
				alt: 'Billing & Channel Engine',
			},
			favicon: '/favicon.svg',
			editLink: {
				baseUrl: 'https://github.com/sulaimanh7877/saas-billing/edit/main/docs/',
			},
			social: [{ icon: 'github', label: 'GitHub', href: repository }],
			customCss: ['./src/styles/custom.css'],
			lastUpdated: true,
			pagination: true,
			sidebar: [
				{
					label: 'Getting started',
					items: [
						'getting-started/installation',
						'getting-started/quickstart',
						'getting-started/tutorial',
					],
				},
				{
					label: 'Guides',
					items: [
						'guides/concepts',
						'guides/catalog',
						'guides/subscriptions',
						'guides/entitlements',
						'guides/billing',
						'guides/partners',
						'guides/reporting',
						'guides/audit-events',
						{ label: 'Use with a coding agent', slug: 'guides/agent-skill' },
					],
				},
				{
					label: 'Deployment',
					items: [
						'deployment/embedded',
						'deployment/rest',
						'deployment/cli',
						'deployment/docker',
					],
				},
				{
					label: 'Reference',
					items: [
						'reference/configuration',
						'reference/rest-api',
						'reference/data-model',
						'reference/errors',
					],
				},
				{
					label: 'Architecture',
					items: [
						'architecture/design',
						'architecture/prefix-strategy',
						{ label: 'ADR 0001 — Prefix strategy', slug: 'adr/0001-prefix-strategy' },
					],
				},
				{ label: 'FAQ', slug: 'faq' },
			],
		}),
	],
});
