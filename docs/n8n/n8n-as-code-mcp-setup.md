# n8n-as-Code MCP Setup Guide

**Setup Date:** May 15, 2026, 9:52 AM (UTC+7)  
**Status:** ✅ INSTALLED  
**Documentation:** https://n8nascode.dev/docs/usage/mcp/

---

## 🎯 What is n8n-as-Code MCP?

The `@n8n-as-code/mcp` is a **complementary offline MCP server** that provides:

- ✅ Full n8n node catalogue (offline, no API needed)
- ✅ 7,000+ community workflow examples
- ✅ Workflow validation using bundled JSON schema
- ✅ n8n documentation search
- ✅ **No network access required** - fully local

**This pairs perfectly with your n8n-mcp instance!**

---

## 📋 Comparison: Two n8n MCPs

| Feature | n8n-mcp | n8n-as-code MCP |
|---------|---------|-----------------|
| **Purpose** | API management | Offline reference |
| **Requires n8n Instance** | ✅ Yes | ❌ No |
| **View Workflows** | ✅ Your instance | ❌ Not applicable |
| **Search Nodes** | Via n8n Cloud | ✅ Offline |
| **Examples** | Via MCP | ✅ 7,000+ templates |
| **Validation** | Real-time | ✅ Offline validation |
| **Network Required** | ✅ Yes | ❌ No |
| **Use Case** | Manage live workflows | Learn & design workflows |

---

## 🔧 Installation & Configuration

### ✅ Already Installed

The n8n-as-code MCP has been added to your Cursor configuration:

**File:** `~/.cursor/mcp.json`

```json
"n8n-as-code": {
  "command": "npx",
  "args": [
    "-y",
    "@n8n-as-code/mcp"
  ]
}
```

### Installation Method

**Method Used:** npx (no persistent install)  
**Alternative:** For faster startup, install globally:

```bash
npm install -g @n8n-as-code/mcp
```

Then use:
```json
"n8n-as-code": {
  "command": "n8nac-mcp"
}
```

---

## 🛠️ Available Tools

### 1. **search_n8n_knowledge**
Search the bundled n8n node catalogue and documentation

**Example:**
```
"Search for webhook nodes"
"Find all HTTP request nodes"
"Show me AI-capable nodes"
```

### 2. **get_n8n_node_info**
Get the full schema and metadata for a specific node

**Example:**
```
"Get info on the HTTP Request node"
"Show schema for Slack node"
"What parameters does the Code node accept?"
```

### 3. **search_n8n_workflow_examples**
Search 7,000+ community workflow examples

**Example:**
```
"Find workflow examples for Slack automation"
"Show me templates that use Google Sheets"
"Search for email workflows"
```

### 4. **get_n8n_workflow_example**
Get metadata and download URL for a specific example

**Example:**
```
"Get the full template for workflow #4031"
"Show me the Slack to Sheets example"
```

### 5. **validate_n8n_workflow**
Validate a workflow against the bundled JSON schema

**Example:**
```
"Validate this workflow configuration"
"Check if this node configuration is valid"
```

### 6. **search_n8n_docs**
Search bundled n8n documentation pages

**Example:**
```
"Find documentation about error handling"
"Show me docs on workflow expressions"
```

---

## 🚀 Usage Examples

### Example 1: Design Phase (Using n8n-as-code)
```
"I want to build a workflow that sends Slack notifications 
when new emails arrive. Show me templates."

→ Uses search_n8n_workflow_examples
→ Returns 7,000+ examples, all locally
→ No API calls, instant results
```

### Example 2: Node Information (Offline)
```
"I need to use the Airtable node. What are the required parameters?"

→ Uses get_n8n_node_info
→ Returns complete schema offline
→ Includes all versions and operations
```

### Example 3: Validation (Offline)
```
"Is this workflow configuration valid?
[paste workflow JSON]"

→ Uses validate_n8n_workflow
→ Validates against bundled schema
→ No network calls
```

### Example 4: Combined Workflow (Using Both MCPs)

1. **Design phase (n8n-as-code):**
   ```
   "Find templates for booking confirmations"
   ```
   → Gets offline examples

2. **Customize phase (n8n-as-code):**
   ```
   "Show me how to add multilingual support to emails"
   ```
   → Gets offline documentation

3. **Deployment phase (n8n-mcp):**
   ```
   "Create this workflow in my n8n instance"
   ```
   → Deploys to your live instance

---

## 🎯 When to Use Each MCP

### Use **n8n-as-code MCP** when:
- ✅ Designing new workflows
- ✅ Learning n8n concepts
- ✅ Searching for examples & templates
- ✅ Validating configurations before deployment
- ✅ You don't have internet access
- ✅ You want instant responses (no API delays)

### Use **n8n-mcp** when:
- ✅ Managing your live workflows
- ✅ Testing workflow execution
- ✅ Viewing execution history
- ✅ Managing credentials
- ✅ Deploying to your instance
- ✅ Checking workflow status

---

## 🔄 Complete Workflow with Both MCPs

```
┌─────────────────────────────────────┐
│ 1. Design Phase                     │
│ n8n-as-code MCP                     │
│ • Search examples                   │
│ • Validate concepts                 │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│ 2. Customization Phase              │
│ n8n-as-code MCP                     │
│ • Get node details                  │
│ • Learn best practices              │
│ • Validate locally                  │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│ 3. Deployment Phase                 │
│ n8n-mcp (Live Instance)             │
│ • Create workflow                   │
│ • Set credentials                   │
│ • Test execution                    │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│ 4. Monitoring Phase                 │
│ n8n-mcp (Live Instance)             │
│ • Check executions                  │
│ • Monitor status                    │
│ • View logs                         │
└─────────────────────────────────────┘
```

---

## 📚 Knowledge Base

Both MCPs provide access to:

**n8n-as-code MCP includes:**
- Complete n8n node catalogue (1,650+ nodes)
- Node schemas and metadata
- 7,000+ workflow examples
- n8n documentation
- Best practices

**Your existing n8n-mcp includes:**
- Your live workflows (100+)
- Execution history
- Credentials management
- Real-time testing
- Workflow management

---

## ⚙️ Configuration Details

### Transport Mode
Using **stdio** (default) - best for local Cursor usage

### Alternative Setup (HTTP - for persistent services)

To run as a persistent HTTP server:

```bash
n8nac-mcp --http --host 0.0.0.0 --port 3000
```

Then in Cursor config:
```json
"n8n-as-code": {
  "url": "http://localhost:3000/mcp"
}
```

### Docker Alternative
Pre-built images available:
```bash
docker run ghcr.io/etiennelescot/n8nac-mcp:latest
```

---

## 🔗 Resource Links

- **Official Docs:** https://n8nascode.dev/docs/usage/mcp/
- **GitHub:** https://github.com/etiennelescot/n8n-as-code
- **npm Package:** https://www.npmjs.com/package/@n8n-as-code/mcp

---

## ✅ Next Steps

1. **Restart Cursor** to load the new MCP
2. Try these commands:
   - "Search for email workflow templates"
   - "Get info on the HTTP Request node"
   - "Find Slack integration examples"
   - "Validate this n8n configuration"

3. **Combine both MCPs:**
   - Design with n8n-as-code (offline)
   - Deploy with n8n-mcp (live instance)

---

## 📊 Your n8n Setup Summary

**You now have TWO complementary n8n MCPs:**

### 1️⃣ **n8n-mcp** (Live Instance)
- ✅ Manages your 100+ live workflows
- ✅ API integration configured
- ✅ Real-time testing & monitoring
- ✅ Credential management

### 2️⃣ **n8n-as-code MCP** (Offline Reference)
- ✅ 7,000+ workflow examples
- ✅ Complete node catalogue
- ✅ Offline validation
- ✅ No network required

**Result:** Complete offline + online n8n workflow automation! 🚀

---

**Setup Completed:** May 15, 2026, 9:52 AM (UTC+7)  
**Configuration File:** `~/.cursor/mcp.json`  
**Status:** ✅ Ready to use after Cursor restart
