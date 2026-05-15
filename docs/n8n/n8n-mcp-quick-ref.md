# n8n-MCP Quick Reference

## 🚀 Common Commands for This Project

Since you're working on an n8n automation project, here are the most useful commands:

## 📋 Essential Workflows

### 1. Start with Tool Documentation
```
Show me all n8n-mcp tools
```
or
```
Get documentation for search_nodes
```

### 2. Find Nodes for Your Use Case
```
Search for nodes related to [your integration]
Examples:
- "Find all webhook trigger nodes"
- "Search for Google Sheets nodes"
- "Find AI and LangChain nodes"
```

### 3. Get Detailed Node Info
```
Show me the HTTP Request node documentation
Get the full details for the Slack node
What are the properties of the Code node?
```

### 4. Search Templates
```
Find templates for [your use case]
Examples:
- "Find simple webhook to Slack workflows"
- "Search for data processing templates"
- "Show me AI agent workflow templates"
```

### 5. Validate Configurations
```
Validate this node configuration: [paste config]
Check this workflow for errors: [paste workflow]
```

## 🎯 For Your AU Group Project

Based on your project files, you might need:

### Workflow Automation Tasks
```
Find templates for project management automation
Search for Jira integration workflows
Find webhook-based notification systems
```

### Data Processing
```
Find templates for data transformation
Search for batch processing workflows
Find nodes for data validation
```

### Integrations
```
Find Slack integration examples
Search for email automation workflows
Find calendar sync templates
```

## 💡 Smart Workflow Building

### Approach 1: Template-First
1. "Find templates for [your goal]"
2. "Show me the top-rated workflow for [task]"
3. "Get the full template for [templateId]"
4. Customize and deploy

### Approach 2: Build from Scratch
1. "Search nodes for [integration]"
2. "Get documentation for [node-type]"
3. "Validate my node configuration"
4. "Build a workflow that [describes your goal]"

## 🔧 If You Have n8n Instance Running

### Connect Your Instance
Add to `~/.cursor/mcp.json`:
```json
"n8n-mcp": {
  "command": "npx",
  "args": ["-y", "n8n-mcp@latest"],
  "env": {
    "N8N_API_URL": "https://your-n8n-instance.com",
    "N8N_API_KEY": "your-api-key"
  }
}
```

### Then Use These Commands
```
List all workflows in my n8n instance
Get workflow [workflow-id]
Create a new workflow [describe it]
Test workflow [workflow-id]
Check execution status
```

## 📊 Node Coverage

The MCP has access to:
- **1,650 nodes total**
  - 820 core nodes
  - 830 community nodes (741 verified)
- **2,352 workflow templates**
- **156 ranked node configurations**
- **265 AI-capable tools**

## 🎨 Popular Nodes to Know

### Triggers
- `n8n-nodes-base.webhook` - Event-driven triggers
- `n8n-nodes-base.scheduleTrigger` - Time-based triggers
- `n8n-nodes-base.manualTrigger` - Manual execution

### Core Nodes
- `n8n-nodes-base.httpRequest` - HTTP API calls
- `n8n-nodes-base.code` - JavaScript/Python scripting
- `n8n-nodes-base.set` - Data transformation
- `n8n-nodes-base.if` - Conditional routing
- `n8n-nodes-base.switch` - Multi-branch routing

### AI & LangChain
- `@n8n/n8n-nodes-langchain.agent` - AI agents
- `@n8n/n8n-nodes-langchain.lmChatOpenAi` - OpenAI chat
- `n8n-nodes-base.openAi` - OpenAI legacy node

### Popular Integrations
- `n8n-nodes-base.slack` - Slack integration
- `n8n-nodes-base.googleSheets` - Google Sheets
- `n8n-nodes-base.gmail` - Gmail automation
- `n8n-nodes-base.telegram` - Telegram bots

## 🎯 Pro Tips for Your Project

1. **Templates First**: With 2,352 templates, someone has probably already built something similar
2. **Validate Early**: Use validation tools before spending time building
3. **Community Nodes**: Search with `source: 'community'` for specialized integrations
4. **Examples**: Add `includeExamples: true` when searching for real-world configs
5. **Parallel Requests**: The MCP handles concurrent requests efficiently

## ⚠️ Safety Reminders

- Always test in development first
- Make backups before AI edits
- Validate before deploying to production
- Keep API credentials secure

## 🔗 Quick Links

- Setup Guide: `n8n-mcp-setup.md` (in this directory)
- GitHub: https://github.com/czlonkowski/n8n-mcp
- Templates: Available via `search_templates`
- Hosted Dashboard: dashboard.n8n-mcp.com

---

**Start building:** Try "Show me available n8n-mcp tools" to see everything you can do!
