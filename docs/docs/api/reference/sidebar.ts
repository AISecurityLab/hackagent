import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

const sidebar: SidebarsConfig = {
  apisidebar: [
    {
      type: "doc",
      id: "api/reference/hackagent-api",
    },
    {
      type: "category",
      label: "Agents",
      link: {
        type: "doc",
        id: "api/reference/agent",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/agent-list",
          label: "List agents",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/agent-create",
          label: "Create an agent",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/agent-retrieve",
          label: "Retrieve an agent",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/agent-update",
          label: "Replace an agent",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/reference/agent-partial-update",
          label: "Update an agent",
          className: "api-method patch",
        },
        {
          type: "doc",
          id: "api/reference/agent-destroy",
          label: "Delete an agent",
          className: "api-method delete",
        },
      ],
    },
    {
      type: "category",
      label: "Campaigns",
      link: {
        type: "doc",
        id: "api/reference/campaign",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/campaign-list",
          label: "List campaigns",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/campaign-create",
          label: "Create a campaign",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/campaign-retrieve",
          label: "Retrieve a campaign",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/campaign-update",
          label: "Replace a campaign",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/reference/campaign-partial-update",
          label: "Update a campaign",
          className: "api-method patch",
        },
        {
          type: "doc",
          id: "api/reference/campaign-destroy",
          label: "Delete a campaign",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/reference/campaign-launch-create",
          label: "Launch a campaign",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/campaign-preflight-retrieve",
          label: "Preflight a campaign launch",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/campaign-launch-adhoc",
          label: "Save and launch a campaign",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/campaign-schema-retrieve",
          label: "Get the campaign spec schema",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/campaign-start-create",
          label: "Start a CLI campaign run",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/campaign-techniques-list",
          label: "List attack techniques",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "Runs",
      link: {
        type: "doc",
        id: "api/reference/run",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/run-list",
          label: "List runs",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/run-retrieve",
          label: "Retrieve a run",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/run-partial-update",
          label: "Annotate a run",
          className: "api-method patch",
        },
        {
          type: "doc",
          id: "api/reference/run-destroy",
          label: "Delete a run",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/reference/run-attempts-retrieve",
          label: "List a goal's attempts",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/run-cancel-create",
          label: "Cancel a campaign run",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/run-children-create",
          label: "Create an attack run",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/run-claim-create",
          label: "Claim a queued run",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/run-compare-retrieve",
          label: "Compare a campaign run with a baseline run",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/run-costs-retrieve",
          label: "Get a campaign run's costs",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/run-finish-create",
          label: "Finish a run",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/run-goals-retrieve",
          label: "List a campaign run's goals",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/run-heartbeat-create",
          label: "Send an executor heartbeat",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/run-matrix-retrieve",
          label: "Get a campaign run's goal matrix",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/run-report-retrieve",
          label: "Get a campaign run's report",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/run-result-create",
          label: "Record a result in a run",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/run-structure-retrieve",
          label: "Get a goal's attack structure",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/run-summary",
          label: "Get a campaign run's summary",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/run-claim-next-create",
          label: "Claim the next cloud run",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/run-delete-selected",
          label: "Delete campaign runs",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/run-summary-list",
          label: "List campaign runs with their verdicts",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "Results",
      link: {
        type: "doc",
        id: "api/reference/result",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/result-list",
          label: "List results",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/result-create",
          label: "Record a result",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/result-retrieve",
          label: "Retrieve a result",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/result-update",
          label: "Replace a result",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/reference/result-partial-update",
          label: "Update a result",
          className: "api-method patch",
        },
        {
          type: "doc",
          id: "api/reference/result-destroy",
          label: "Delete a result",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/reference/result-trace-create",
          label: "Add a trace step to a result",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "Attack configurations",
      link: {
        type: "doc",
        id: "api/reference/attack",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/attack-list",
          label: "List attack configurations",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/attack-create",
          label: "Create an attack configuration",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/attack-retrieve",
          label: "Retrieve an attack configuration",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/attack-update",
          label: "Replace an attack configuration",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/reference/attack-partial-update",
          label: "Update an attack configuration",
          className: "api-method patch",
        },
        {
          type: "doc",
          id: "api/reference/attack-destroy",
          label: "Delete an attack configuration",
          className: "api-method delete",
        },
      ],
    },
    {
      type: "category",
      label: "Secrets",
      link: {
        type: "doc",
        id: "api/reference/secret",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/secret-list",
          label: "List secrets",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/secret-create",
          label: "Set a secret",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/secret-update",
          label: "Replace a secret's value",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/reference/secret-destroy",
          label: "Delete a secret",
          className: "api-method delete",
        },
      ],
    },
    {
      type: "category",
      label: "LLM gateway",
      link: {
        type: "doc",
        id: "api/reference/generate",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/v-1-chat-completions-create",
          label: "Create a chat completion",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/v-1-models-retrieve",
          label: "List gateway models",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "API keys",
      link: {
        type: "doc",
        id: "api/reference/key",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/key-list",
          label: "List API keys",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/key-create",
          label: "Create an API key",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/key-retrieve",
          label: "Retrieve an API key",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/key-destroy",
          label: "Delete an API key",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/reference/key-context-retrieve",
          label: "Get the caller's identity",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "Usage logs",
      link: {
        type: "doc",
        id: "api/reference/apilogs",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/apilogs-list",
          label: "List gateway usage logs",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/apilogs-retrieve",
          label: "Retrieve a gateway usage log",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/apilogs-summary-retrieve",
          label: "Summarize gateway usage by day",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "Organizations",
      link: {
        type: "doc",
        id: "api/reference/organization",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/organization-list",
          label: "List organizations",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/organization-create",
          label: "Create an organization",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/organization-retrieve",
          label: "Retrieve an organization",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/organization-update",
          label: "Replace an organization",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/reference/organization-partial-update",
          label: "Update an organization",
          className: "api-method patch",
        },
        {
          type: "doc",
          id: "api/reference/organization-destroy",
          label: "Delete an organization",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/reference/organization-me-retrieve",
          label: "Get the caller's organization",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "Users",
      link: {
        type: "doc",
        id: "api/reference/user",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/user-list",
          label: "List user profiles",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/user-create",
          label: "Create a user profile",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reference/user-retrieve",
          label: "Retrieve a user profile",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/user-update",
          label: "Replace a user profile",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/reference/user-partial-update",
          label: "Update a user profile",
          className: "api-method patch",
        },
        {
          type: "doc",
          id: "api/reference/user-destroy",
          label: "Delete a user profile",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/reference/user-me-retrieve",
          label: "Get the caller's profile",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/reference/user-me-update",
          label: "Update the caller's profile",
          className: "api-method put",
        },
      ],
    },
    {
      type: "category",
      label: "Credits",
      link: {
        type: "doc",
        id: "api/reference/credits",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/credits-request-create",
          label: "Request more credits",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "License",
      link: {
        type: "doc",
        id: "api/reference/license",
      },
      items: [
        {
          type: "doc",
          id: "api/reference/license-update",
          label: "Install a license",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/reference/license-status-retrieve",
          label: "Get the license status",
          className: "api-method get",
        },
      ],
    },
  ],
};

export default sidebar.apisidebar;
